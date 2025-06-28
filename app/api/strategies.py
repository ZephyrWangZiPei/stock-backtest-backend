from flask import request
from flask_restx import Namespace, Resource, fields
from app.models import Strategy
from app.strategies import STRATEGY_MAP, get_strategy_by_identifier
from .responses import api_success, get_api_list_response_model, get_api_response_model

ns = Namespace('strategies', description='交易策略管理接口')

# region 数据模型
strategy_model = ns.model('Strategy', {
    'id': fields.Integer(readonly=True, description='策略的唯一ID'),
    'name': fields.String(required=True, description='策略的名称'),
    'identifier': fields.String(required=True, description='策略的唯一标识符')
})

parameter_definition_model = ns.model('ParameterDefinition', {
    'name': fields.String(description='参数名称'),
    'label': fields.String(description='参数显示标签'),
    'type': fields.String(description='参数类型 (e.g., number, string)'),
    'default': fields.Raw(description='参数默认值'),
    'description': fields.String(description='参数描述')
})

strategy_details_model = ns.model('StrategyDetails', {
    'name': fields.String(description='策略名称'),
    'identifier': fields.String(description='策略唯一标识符'),
    'description': fields.String(description='策略的详细描述'),
    'parameter_definitions': fields.List(fields.Nested(parameter_definition_model), description='参数定义列表')
})

strategy_list_model = ns.model('StrategyList', {
    'id': fields.Integer(readonly=True, description='策略ID'),
    'name': fields.String(required=True, description='策略名称'),
    'description': fields.String(description='策略描述'),
    'identifier': fields.String(required=True, description='策略的唯一标识符'),
})

strategy_detail_model = ns.clone('StrategyDetail', strategy_list_model, {
    'parameter_definitions': fields.List(fields.Nested(parameter_definition_model), description='参数定义列表')
})

# 标准化响应模型
strategy_list_response = get_api_list_response_model(ns, strategy_list_model)
strategy_detail_response = get_api_response_model(ns, strategy_detail_model)
# endregion

@ns.route('/')
class StrategyListResource(Resource):
    @ns.doc('获取策略列表')
    def get(self):
        """获取所有可用的交易策略"""
        strategies = Strategy.query.order_by(Strategy.id).all()
        # 直接使用 to_dict() 转换模型，并用 api_success 包装
        return api_success(data=[s.to_dict() for s in strategies])

@ns.route('/<string:identifier>')
@ns.param('identifier', '策略的唯一标识符')
class StrategyDetails(Resource):
    @ns.doc('获取单个策略的详情，包括参数定义和描述')
    def get(self, identifier):
        """获取单个策略的详情，包括参数定义和描述"""
        strategy_class = get_strategy_by_identifier(identifier)
        if not strategy_class:
            ns.abort(404, "Strategy not found")
        
        data = {
            "name": strategy_class.get_name(),
            "identifier": strategy_class.get_identifier(),
            "description": strategy_class.get_description(),
            "parameter_definitions": strategy_class.get_parameter_definitions()
        }
        return api_success(data=data)

    @ns.doc('创建策略')
    @ns.expect(strategy_detail_model)
    def post(self):
        """创建新的交易策略"""
        return {
            'success': True,
            'message': '策略创建接口开发中',
            'data': None
        } 