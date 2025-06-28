from flask import request
from flask_restx import Namespace, Resource, fields
from app.models import BacktestResult, Strategy, Stock
from app.backtester.engine import BacktestEngine
from app import db
import logging
from .responses import api_success, get_api_response_model
import json
from app.scheduler import scheduler

logger = logging.getLogger(__name__)

ns = Namespace('backtests', description='策略回测接口')

# region 数据模型
backtest_result_model = ns.model('BacktestResultData', {
    'id': fields.Integer(description='回测ID'),
    'strategy_id': fields.Integer(description='策略ID'),
    'start_date': fields.String(description='开始日期'),
    'end_date': fields.String(description='结束日期'),
    'initial_capital': fields.Float(description='初始资金'),
    'final_capital': fields.Float(description='最终资金'),
    'total_return': fields.Float(description='总收益率'),
    'annual_return': fields.Float(description='年化收益率'),
    'max_drawdown': fields.Float(description='最大回撤'),
    'sharpe_ratio': fields.Float(description='夏普比率'),
    'status': fields.String(description='回测状态'),
    'portfolio_history': fields.Raw(description='每日资产组合历史'),
    'trades': fields.Raw(description='交易记录'),
})

backtest_input_model = ns.model('BacktestInput', {
    'strategy_id': fields.Integer(required=True, description='策略的ID'),
    'start_date': fields.String(required=True, description='回测开始日期 (YYYY-MM-DD)'),
    'end_date': fields.String(required=True, description='回测结束日期 (YYYY-MM-DD)'),
    'initial_capital': fields.Float(required=True, description='初始资金'),
    'stock_codes': fields.List(fields.String, required=True, description='用于回测的股票代码列表'),
    'parameters': fields.Raw(description='策略的自定义参数 (JSON对象)', required=False)
})

backtest_response_data_model = ns.model('BacktestResponseData', {
    'backtest_id': fields.Integer(description='新创建的回测任务ID')
})

# 标准化响应模型
backtest_start_response = get_api_response_model(ns, backtest_response_data_model)
backtest_result_response = get_api_response_model(ns, backtest_result_model)
# endregion

@ns.route('/')
class BacktestRun(Resource):
    @ns.expect(backtest_input_model)
    @ns.marshal_with(backtest_start_response, code=202)
    def post(self):
        """启动一个新的回测任务"""
        data = request.get_json()
        
        if not Strategy.query.get(data['strategy_id']):
            ns.abort(404, f"Strategy with id {data['strategy_id']} not found")

        stocks_count = Stock.query.filter(Stock.code.in_(data['stock_codes'])).count()
        if stocks_count != len(data['stock_codes']):
            ns.abort(404, 'One or more stock codes are invalid')

        engine = BacktestEngine(
            strategy_id=data['strategy_id'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            initial_capital=data['initial_capital'],
            stock_codes=data['stock_codes'],
            custom_parameters=data.get('parameters')
        )
        
        try:
            backtest_id = engine.run()
        except Exception as e:
            logger.error(f"回测执行失败: {e}", exc_info=True)
            ns.abort(500, 'An unexpected error occurred during backtest execution.')

        if backtest_id is None:
            ns.abort(400, 'Failed to start backtest, no data found for the given stocks in the specified date range.')
        
        return api_success(data={'backtest_id': backtest_id}, message='Backtest started successfully', code=202)

@ns.route('/<int:id>')
@ns.param('id', 'The backtest result identifier')
class BacktestResultResource(Resource):
    @ns.doc('get_backtest_result')
    def get(self, id):
        """获取单个回测结果"""
        result = BacktestResult.query.get_or_404(id)
        
        # 当任务完成时，确保返回包含交易记录的完整数据
        if result.status == 'completed':
            data = result.to_dict(include_trades=True)
        else:
            data = result.to_dict()

        return api_success(data=data) 