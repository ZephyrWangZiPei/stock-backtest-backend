from flask_restx import Namespace, Resource
import logging
from app.models import Stock, BacktestResult, Strategy

logger = logging.getLogger(__name__)

ns = Namespace('stats', description='系统统计数据接口')

@ns.route('/')
class SystemStats(Resource):
    @ns.doc('获取系统核心统计数据')
    def get(self):
        """提供核心系统统计数据"""
        try:
            total_stocks = Stock.query.count()
            total_backtests = BacktestResult.query.count()
            total_strategies = Strategy.query.count()
            
            # 自选股数量从前端localStorage获取，此处不提供
            
            return {
                'success': True,
                'message': '获取系统统计数据成功',
                'data': {
                    'total_stocks': total_stocks,
                    'total_backtests': total_backtests,
                    'total_strategies': total_strategies,
                }
            }
        except Exception as e:
            logger.error(f"获取系统统计数据失败: {e}")
            return {'success': False, 'message': f'服务器错误: {str(e)}'}, 500 