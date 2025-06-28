from flask import request
from flask_restx import Namespace, Resource, fields

ns = Namespace('realtime', description='实时数据接口')

# 定义数据模型
realtime_model = ns.model('RealtimeData', {
    'id': fields.Integer(description='数据ID'),
    'stock_code': fields.String(description='股票代码'),
    'current_price': fields.Float(description='当前价格'),
    'open_price': fields.Float(description='开盘价'),
    'high_price': fields.Float(description='最高价'),
    'low_price': fields.Float(description='最低价'),
    'pre_close': fields.Float(description='昨收价'),
    'change_amount': fields.Float(description='涨跌额'),
    'change_rate': fields.Float(description='涨跌幅'),
    'volume': fields.Integer(description='成交量'),
    'amount': fields.Float(description='成交额'),
    'quote_time': fields.String(description='行情时间')
})

@ns.route('/<string:code>')
class RealtimeStock(Resource):
    @ns.doc('获取股票实时数据')
    def get(self, code):
        """获取指定股票的实时数据"""
        return {
            'success': True,
            'message': '实时数据接口开发中',
            'data': {
                'stock_code': code,
                'current_price': 0.0,
                'change_rate': 0.0
            }
        }

@ns.route('/batch')
class RealtimeBatch(Resource):
    @ns.doc('批量获取实时数据')
    @ns.param('codes', '股票代码列表，逗号分隔', type=str, required=True)
    def get(self):
        """批量获取多只股票的实时数据"""
        codes = request.args.get('codes', '').split(',')
        return {
            'success': True,
            'message': '批量实时数据接口开发中',
            'data': {code: {'stock_code': code, 'current_price': 0.0} for code in codes if code}
        } 