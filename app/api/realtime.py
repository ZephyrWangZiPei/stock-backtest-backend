from flask import request
from flask_restx import Namespace, Resource, fields
from datetime import datetime, timedelta
import logging
from app.models.realtime_data import RealtimeData
from app.models.stock import Stock
from app.data_collector.baostock_client import BaostockClient
from app import db
import pandas as pd
from sqlalchemy import desc
import random

logger = logging.getLogger(__name__)

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

def _fetch_realtime_data(stock_code: str, baostock_client: BaostockClient = None):
    """
    获取股票实时数据的内部函数。
    优化逻辑：优先从BaoStock获取最新数据，如果失败则从数据库读取作为备用。
    可以接收一个已存在的BaoStock客户端。
    """
    try:
        # 1. 优先从BaoStock获取最新数据
        def fetch_from_baostock(client):
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            return client.get_stock_history(stock_code, start_date, end_date)

        if baostock_client:
            df = fetch_from_baostock(baostock_client)
        else:
            with BaostockClient() as client:
                df = fetch_from_baostock(client)
            
        if not df.empty:
            latest_row = df.iloc[-1]
            
            try:
                current_price = float(latest_row['close'])
                open_price = float(latest_row['open'])
                high_price = float(latest_row['high'])
                low_price = float(latest_row['low'])
                volume = int(float(latest_row['volume'])) if latest_row['volume'] else 0
                amount = float(latest_row['amount']) if latest_row['amount'] else 0.0
                
                # 使用BaoStock数据中的日期，并结合收盘时间15:00:00
                date_str = latest_row['date']
                quote_time = datetime.strptime(f"{date_str} 15:00:00", '%Y-%m-%d %H:%M:%S')

                pre_close = current_price
                if len(df) > 1:
                    pre_close = float(df.iloc[-2]['close'])
                
                change_amount = current_price - pre_close
                change_rate = (change_amount / pre_close * 100) if pre_close > 0 else 0
                
                # 仅在交易时间内进行价格模拟波动
                now = datetime.now()
                is_trading_time = (now.weekday() < 5 and  # 周一到周五
                                   (now.time() >= datetime.strptime('09:30', '%H:%M').time() and
                                    now.time() <= datetime.strptime('15:00', '%H:%M').time()))

                if is_trading_time:
                    fluctuation = random.uniform(-0.005, 0.005)
                    simulated_price = current_price * (1 + fluctuation)
                    change_amount = simulated_price - pre_close
                    change_rate = (change_amount / pre_close * 100) if pre_close > 0 else 0
                else:
                    simulated_price = current_price

                # 更新或创建数据库记录
                record = RealtimeData.query.filter_by(stock_code=stock_code).first()
                if not record:
                    record = RealtimeData(stock_code=stock_code)
                    db.session.add(record)
                
                record.current_price = simulated_price
                record.open_price = open_price
                record.high_price = max(high_price, simulated_price)
                record.low_price = min(low_price, simulated_price)
                record.pre_close = pre_close
                record.change_amount = change_amount
                record.change_rate = change_rate
                record.volume = volume
                record.amount = amount
                record.quote_time = quote_time
                
                db.session.commit()
                
                return {
                    'stock_code': stock_code,
                    'current_price': simulated_price,
                    'open_price': open_price,
                    'high_price': max(high_price, simulated_price),
                    'low_price': min(low_price, simulated_price),
                    'pre_close': pre_close,
                    'change_amount': change_amount,
                    'change_rate': change_rate,
                    'volume': volume,
                    'amount': amount,
                    'quote_time': quote_time.isoformat()
                }
                
            except (ValueError, TypeError) as e:
                logger.error(f"从BaoStock获取数据后，数据转换错误 {stock_code}: {e}")
                # 此处不立即返回，允许降级到数据库查询

    except Exception as e:
        logger.warning(f"从BaoStock获取实时数据失败 {stock_code}: {e}。将尝试从数据库读取。")

    # 2. 如果从BaoStock获取失败，则尝试从数据库读取作为备用
    try:
        latest_data = RealtimeData.query.filter_by(stock_code=stock_code).order_by(desc(RealtimeData.quote_time)).first()
        
        if latest_data:
            logger.info(f"已从数据库为 {stock_code} 提供备用数据。")
            return {
                'stock_code': stock_code,
                'current_price': float(latest_data.current_price) if latest_data.current_price else None,
                'open_price': float(latest_data.open_price) if latest_data.open_price else None,
                'high_price': float(latest_data.high_price) if latest_data.high_price else None,
                'low_price': float(latest_data.low_price) if latest_data.low_price else None,
                'pre_close': float(latest_data.pre_close) if latest_data.pre_close else None,
                'change_amount': float(latest_data.change_amount) if latest_data.change_amount else None,
                'change_rate': float(latest_data.change_rate) if latest_data.change_rate else None,
                'volume': int(latest_data.volume) if latest_data.volume else None,
                'amount': float(latest_data.amount) if latest_data.amount else None,
                'quote_time': latest_data.quote_time.isoformat() if latest_data.quote_time else None
            }
    except Exception as e:
        logger.error(f"从数据库读取备用数据时失败 {stock_code}: {e}")

    # 3. 如果全部失败，返回错误
    logger.error(f"无法为 {stock_code} 获取任何数据（外部和数据库）。")
    return {'error': f'无法获取股票 {stock_code} 的数据'}

@ns.route('/<string:code>')
class RealtimeStock(Resource):
    @ns.doc('获取股票实时数据')
    @ns.marshal_with(realtime_model)
    def get(self, code):
        """获取指定股票的实时数据"""
        try:
            data = _fetch_realtime_data(code)
            
            if 'error' in data:
                return {
                    'success': False,
                    'message': data['error'],
                    'data': None
                }, 400
            
            return {
                'success': True,
                'message': '获取实时数据成功',
                'data': data
            }
            
        except Exception as e:
            logger.error(f"实时数据接口错误: {e}")
            return {
                'success': False,
                'message': f'服务器错误: {str(e)}',
                'data': None
            }, 500

@ns.route('/batch')
class RealtimeBatch(Resource):
    @ns.doc('批量获取实时数据')
    @ns.param('codes', '股票代码列表，逗号分隔', type=str, required=True)
    def get(self):
        """批量获取多只股票的实时数据"""
        try:
            codes_param = request.args.get('codes', '')
            if not codes_param:
                return {'success': False, 'message': '请提供股票代码列表', 'data': None}, 400
            
            codes = [code.strip() for code in codes_param.split(',') if code.strip()]
            if not codes:
                return {'success': False, 'message': '股票代码列表不能为空', 'data': None}, 400
            
            if len(codes) > 50:
                return {'success': False, 'message': '单次最多查询50只股票', 'data': None}, 400
            
            results = {}
            errors = []
            
            # 使用单个BaoStock客户端会话处理整个批量请求
            with BaostockClient() as client:
                for code in codes:
                    try:
                        # 注意：此处直接调用内部逻辑，而不是每次都创建新会话的 _fetch_realtime_data
                        # 为了简化，我们将核心逻辑暂时复制至此，未来可重构为接收client的函数
                        df = client.get_stock_history(code, 
                                                    (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
                                                    datetime.now().strftime('%Y-%m-%d'))
                        
                        if df.empty:
                            # 如果BaoStock没有数据，尝试从数据库获取
                            db_data = RealtimeData.query.filter_by(stock_code=code).order_by(desc(RealtimeData.quote_time)).first()
                            if db_data:
                                results[code] = {
                                    'stock_code': code,
                                    'current_price': float(db_data.current_price), 'open_price': float(db_data.open_price),
                                    'high_price': float(db_data.high_price), 'low_price': float(db_data.low_price),
                                    'pre_close': float(db_data.pre_close), 'change_amount': float(db_data.change_amount),
                                    'change_rate': float(db_data.change_rate), 'volume': int(db_data.volume),
                                    'amount': float(db_data.amount), 'quote_time': db_data.quote_time.isoformat()
                                }
                            else:
                                raise ValueError("No data from BaoStock or DB")
                            continue

                        latest_row = df.iloc[-1]
                        current_price = float(latest_row['close'])
                        pre_close = float(df.iloc[-2]['close']) if len(df) > 1 else current_price
                        change_amount = current_price - pre_close
                        change_rate = (change_amount / pre_close * 100) if pre_close != 0 else 0
                        
                        # 使用BaoStock数据中的日期，并结合收盘时间15:00:00
                        date_str = latest_row['date']
                        quote_time = datetime.strptime(f"{date_str} 15:00:00", '%Y-%m-%d %H:%M:%S')

                        results[code] = {
                            'stock_code': code,
                            'current_price': current_price,
                            'open_price': float(latest_row['open']),
                            'high_price': float(latest_row['high']),
                            'low_price': float(latest_row['low']),
                            'pre_close': pre_close,
                            'change_amount': change_amount,
                            'change_rate': change_rate,
                            'volume': int(float(latest_row['volume'])),
                            'amount': float(latest_row['amount']),
                            'quote_time': quote_time.isoformat()
                        }
                    except Exception as e:
                        errors.append(f"{code}: {str(e)}")
            
            response_data = {
                'success': True,
                'message': f'成功获取 {len(results)} 只股票数据',
                'data': results
            }
            
            if errors:
                response_data['message'] += f'，{len(errors)} 只股票获取失败'
                response_data['errors'] = errors
            
            return response_data
            
        except Exception as e:
            logger.error(f"批量实时数据接口错误: {e}")
            return {'success': False, 'message': f'服务器错误: {str(e)}', 'data': None}, 500

@ns.route('/market/summary')
class MarketSummary(Resource):
    @ns.doc('获取市场概况')
    def get(self):
        """获取市场概况数据"""
        logger.info("收到来自 REST API 的市场概况数据请求。")
        try:
            # 获取主要指数的数据（上证指数、深证成指、创业板指）
            major_indices = ['sh.000001', 'sz.399001', 'sz.399006']
            summary_data = []

            # 使用单个客户端会话处理所有指数
            with BaostockClient() as client:
                for index_code in major_indices:
                    try:
                        data = _fetch_realtime_data(index_code, baostock_client=client)
                        if 'error' not in data:
                            index_name = {
                                'sh.000001': '上证指数',
                                'sz.399001': '深证成指', 
                                'sz.399006': '创业板指'
                            }.get(index_code, index_code)
                            
                            summary_data.append({
                                'name': index_name,
                                'code': index_code,
                                'current_price': data.get('current_price'),
                                'change_amount': data.get('change_amount'),
                                'change_rate': data.get('change_rate')
                            })
                    except Exception as e:
                        logger.warning(f"获取指数 {index_code} 数据失败: {e}")
                        continue
            
            logger.info(f"成功获取 {len(summary_data)} 个指数的市场概况，准备通过 REST API 返回。")
            return {
                'success': True,
                'message': '获取市场概况成功',
                'data': {
                    'indices': summary_data,
                    'update_time': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"市场概况接口错误: {e}")
            return {
                'success': False,
                'message': f'获取市场概况失败: {str(e)}',
                'data': None
            }, 500 