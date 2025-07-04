from flask_restx import Namespace, Resource, fields
from app.api.responses import api_success, get_api_response_model
from app.jobs.top_strategy_backtest_job import backtest_potential_stocks
import logging

logger = logging.getLogger(__name__)

ns = Namespace('top-backtest', description='潜力股多策略回测接口')

# 定义返回数据结构：{ strategy_identifier: [ {code, win_rate} ] }
stock_entry = ns.model('TopStockEntry', {
    'code': fields.String(description='股票代码'),
    'win_rate': fields.Float(description='胜率'),
})

summary_model = ns.model('TopBacktestSummary', {
    'strategy': fields.String(description='策略 identifier'),
    'top_list': fields.List(fields.Nested(stock_entry))
})

response_model = get_api_response_model(ns, summary_model)

@ns.route('/')
class RunTopBacktest(Resource):
    @ns.doc('run_top_backtest')
    @ns.marshal_with(response_model, code=200)
    def get(self):
        """
        立即执行多策略回测并返回各策略胜率 Top 结果。
        
        ⚠️ 注意：此API已废弃，不推荐使用！
        
        原因：
        1. 同步执行，可能导致请求超时
        2. 不包含DeepSeek AI分析功能
        3. 不保存结果到数据库
        4. 可能与异步任务产生冲突
        
        推荐使用：POST /api/jobs/run/top_strategy_backtest
        该API提供异步执行、进度提示、AI分析和数据库保存功能。
        """
        logger.warning("⚠️ 使用了已废弃的同步Top回测API，建议使用异步任务API: /api/jobs/run/top_strategy_backtest")
        
        try:
            summary = backtest_potential_stocks()
            return api_success(data=summary, message='回测完成 (建议使用异步任务API)')
        except Exception as e:
            logger.error(f'执行 Top Backtest 失败: {e}', exc_info=True)
            ns.abort(500, 'Server error') 