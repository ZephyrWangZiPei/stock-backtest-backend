from flask import request
from flask_restx import Namespace, Resource, fields

ns = Namespace('watchlist', description='自选股管理接口')

# 定义数据模型
watchlist_model = ns.model('UserWatchlist', {
    'id': fields.Integer(description='自选股ID'),
    'user_id': fields.String(description='用户ID'),
    'stock_id': fields.Integer(description='股票ID'),
    'stock': fields.Raw(description='股票信息'),
    'alert_price_high': fields.Float(description='价格上限提醒'),
    'alert_price_low': fields.Float(description='价格下限提醒'),
    'notes': fields.String(description='备注'),
    'tags': fields.List(fields.String, description='标签'),
    'created_at': fields.String(description='创建时间')
})

@ns.route('/')
class WatchlistList(Resource):
    @ns.doc('获取自选股列表')
    @ns.param('user_id', '用户ID', type=str, required=True)
    def get(self):
        """获取用户自选股列表"""
        return {
            'success': True,
            'message': '自选股接口开发中',
            'data': []
        }
    
    @ns.doc('添加自选股')
    @ns.expect(watchlist_model)
    def post(self):
        """添加股票到自选股"""
        return {
            'success': True,
            'message': '自选股添加接口开发中',
            'data': None
        } 