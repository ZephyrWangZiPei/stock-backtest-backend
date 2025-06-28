from flask_restx import fields

def get_api_response_model(ns, data_model):
    """为单个数据对象创建标准化的API响应模型。"""
    return ns.model(f'{data_model.name}ApiResponse', {
        'code': fields.Integer(default=200, description='状态码'),
        'message': fields.String(default='success', description='响应消息'),
        'data': fields.Nested(data_model, description='响应数据')
    })

def get_api_list_response_model(ns, item_model):
    """为数据对象列表创建标准化的API响应模型。"""
    return ns.model(f'{item_model.name}ListApiResponse', {
        'code': fields.Integer(default=200, description='状态码'),
        'message': fields.String(default='success', description='响应消息'),
        'data': fields.List(fields.Nested(item_model), description='数据列表')
    })

def get_pagination_model(ns, items_model):
    """为分页数据创建数据模型。"""
    return ns.model(f'{items_model.name}Pagination', {
        'items': fields.List(fields.Nested(items_model)),
        'page': fields.Integer,
        'per_page': fields.Integer,
        'total_pages': fields.Integer,
        'total_items': fields.Integer
    })

def api_success(data=None, message='success', code=200):
    """格式化一个成功的API响应。"""
    response = {
        'code': code,
        'message': message,
    }
    if data is not None:
        response['data'] = data
    return response

def api_error(message='error', code=500, data=None):
    """格式化一个失败的API响应。"""
    response = {
        'code': code,
        'message': message,
    }
    if data is not None:
        response['data'] = data
    return response, code 