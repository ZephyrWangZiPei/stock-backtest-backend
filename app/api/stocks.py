from flask import request
from flask_restx import Namespace, Resource, fields
from app import db
from app.models import Stock, DailyData
from sqlalchemy import desc, and_
from datetime import datetime
from .responses import api_success, api_error

ns = Namespace('stocks', description='股票基础数据接口')

# 定义数据模型用于文档生成
stock_model = ns.model('Stock', {
    'id': fields.Integer(description='股票ID'),
    'code': fields.String(required=True, description='股票代码'),
    'name': fields.String(required=True, description='股票名称'),
    'market': fields.String(required=True, description='市场(SH/SZ)'),
    'industry': fields.String(description='所属行业'),
    'sector': fields.String(description='所属板块'),
    'list_date': fields.String(description='上市日期'),
    'is_active': fields.Boolean(description='是否活跃'),
    'stock_type': fields.String(description='类型: stock/etf'),
    'created_at': fields.String(description='创建时间'),
    'updated_at': fields.String(description='更新时间')
})

daily_data_model = ns.model('DailyData', {
    'id': fields.Integer(description='数据ID'),
    'stock_id': fields.Integer(description='股票ID'),
    'trade_date': fields.String(description='交易日期'),
    'open_price': fields.Float(description='开盘价'),
    'high_price': fields.Float(description='最高价'),
    'low_price': fields.Float(description='最低价'),
    'close_price': fields.Float(description='收盘价'),
    'volume': fields.Integer(description='成交量'),
    'amount': fields.Float(description='成交额'),
    'adj_close': fields.Float(description='后复权收盘价'),
    'ma5': fields.Float(description='5日均线'),
    'ma10': fields.Float(description='10日均线'),
    'ma20': fields.Float(description='20日均线'),
    'ma60': fields.Float(description='60日均线')
})

pagination_model = ns.model('Pagination', {
    'page': fields.Integer(description='当前页码'),
    'per_page': fields.Integer(description='每页数量'),
    'total': fields.Integer(description='总记录数'),
    'pages': fields.Integer(description='总页数')
})

stocks_response_model = ns.model('StocksResponse', {
    'data': fields.List(fields.Nested(stock_model)),
    'pagination': fields.Nested(pagination_model),
    'success': fields.Boolean(description='请求是否成功'),
    'message': fields.String(description='响应消息')
})

@ns.route('/')
class StockList(Resource):
    @ns.doc('获取股票列表')
    @ns.param('page', '页码', type=int, default=1)
    @ns.param('per_page', '每页数量', type=int, default=20)
    @ns.param('market', '市场过滤(SH/SZ)', type=str)
    @ns.param('industry', '行业过滤', type=str)
    @ns.param('stock_type', '类型过滤(stock/etf)', type=str)
    @ns.param('keyword', '关键词搜索(代码或名称)', type=str)
    def get(self):
        """获取股票列表"""
        try:
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 20, type=int), 100)
            market = request.args.get('market')
            industry = request.args.get('industry')
            stock_type = request.args.get('stock_type')
            keyword = request.args.get('keyword')
            
            query = Stock.query

            if keyword:
                # 将关键词拆分，并要求每个词都在名称或代码中出现
                search_terms = keyword.split()
                conditions = []
                for term in search_terms:
                    conditions.append(
                        db.or_(
                            Stock.code.like(f'%{term}%'),
                            Stock.name.like(f'%{term}%')
                        )
                    )
                query = query.filter(db.and_(*conditions))
            
            # 分页查询
            pagination = query.order_by(Stock.code).paginate(
                page=page, 
                per_page=per_page, 
                error_out=False
            )
            
            data = {
                'items': [stock.to_dict() for stock in pagination.items],
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total_items': pagination.total,
                'total_pages': pagination.pages
            }
            return api_success(data, message="股票列表获取成功")
        except Exception as e:
            return api_error(str(e))

@ns.route('/<string:code>')
class StockDetail(Resource):
    @ns.doc('获取股票详情')
    @ns.marshal_with(stock_model)
    def get(self, code):
        """根据股票代码获取详情"""
        try:
            stock = Stock.query.filter_by(code=code).first()
            if not stock:
                return {'success': False, 'message': '股票不存在'}, 404
            
            return stock.to_dict()
        except Exception as e:
            return {'success': False, 'message': f'获取失败: {str(e)}'}, 500

@ns.route('/<string:code>/daily')
@ns.param('code', '股票代码，例如 sh.600036')
class StockDailyData(Resource):
    @ns.doc('获取股票日线数据')
    @ns.param('start_date', '开始日期 (YYYY-MM-DD)', 'query')
    @ns.param('end_date', '结束日期 (YYYY-MM-DD)', 'query')
    def get(self, code):
        """获取指定股票在一段时间内的日线数据"""
        stock = Stock.query.filter_by(code=code).first_or_404()
        
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        query = DailyData.query.filter_by(stock_id=stock.id)

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(DailyData.trade_date >= start_date)
        
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(DailyData.trade_date <= end_date)
            
        daily_data = query.order_by(DailyData.trade_date).all()
        
        return api_success([d.to_dict() for d in daily_data], message="日线数据获取成功")

@ns.route('/industries')
class IndustryList(Resource):
    @ns.doc('获取行业列表')
    def get(self):
        """获取所有行业列表"""
        try:
            industries = db.session.query(Stock.industry).filter(
                Stock.industry.isnot(None),
                Stock.is_active == True
            ).distinct().all()
            
            industry_list = [industry[0] for industry in industries if industry[0]]
            
            return {
                'data': sorted(industry_list),
                'success': True,
                'message': '获取成功'
            }
        except Exception as e:
            return {'success': False, 'message': f'获取失败: {str(e)}'}, 500 