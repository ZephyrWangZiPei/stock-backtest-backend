from flask import request
from flask_restx import Namespace, Resource, fields
from app.models.stock import Stock

ns = Namespace('query', description='数据查询接口')

# 自定义一个格式化日期时间字段
class FormattedDateTime(fields.Raw):
    def format(self, value):
        return value.strftime('%Y-%m-%d %H:%M:%S') if value else None

# 列表查询的请求参数模型
list_query_parser = ns.parser()
list_query_parser.add_argument('page', type=int, default=1, help='页码')
list_query_parser.add_argument('per_page', type=int, default=20, help='每页数量')
list_query_parser.add_argument('name', type=str, help='按名称模糊搜索')

# 单个股票模型
stock_model = ns.model('Stock', {
    'code': fields.String(description='股票代码'),
    'name': fields.String(description='股票名称'),
    'industry': fields.String(description='所属行业'),
    'market': fields.String(description='市场类型'),
    'list_date': fields.Date(description='上市日期'),
    'created_at': FormattedDateTime(description='创建时间'),
    'updated_at': FormattedDateTime(description='更新时间'),
})

# 分页响应模型
pagination_model = ns.model('Pagination', {
    'items': fields.List(fields.Nested(stock_model)),
    'page': fields.Integer(description='当前页码'),
    'pages': fields.Integer(description='总页数'),
    'per_page': fields.Integer(description='每页数量'),
    'total': fields.Integer(description='总记录数'),
})

@ns.route('/stocks')
class StockList(Resource):
    @ns.doc('获取股票基础信息列表')
    @ns.expect(list_query_parser)
    @ns.marshal_with(pagination_model)
    def get(self):
        """分页获取股票基础信息列表"""
        args = list_query_parser.parse_args()
        page = args.get('page')
        per_page = args.get('per_page')
        name_search = args.get('name')

        query = Stock.query

        if name_search:
            query = query.filter(Stock.name.like(f'%{name_search}%'))

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'items': pagination.items,
            'page': pagination.page,
            'pages': pagination.pages,
            'per_page': pagination.per_page,
            'total': pagination.total,
        } 