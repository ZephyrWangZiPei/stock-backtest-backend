from flask import Blueprint, current_app, request, Response
from flask_restx import Api, Resource, fields
from app.api.responses import api_success, api_error
from app.models import Stock, DailyData, TopStrategyStock, Strategy # 导入股票、日线数据、Top策略股票和策略模型
from app.strategies.rsi_strategy import RsiStrategy
from app.strategies.macd_strategy import MacdStrategy
from app.strategies.dual_moving_average import DualMovingAverageStrategy # 导入策略类
import pandas as pd
from datetime import datetime, timedelta
import json # 用于解析DeepSeek的JSON输出

# 创建蓝图
deepseek_bp = Blueprint('deepseek_api', __name__, url_prefix='/api/deepseek')
api = Api(deepseek_bp, doc='/doc',
          title='DeepSeek API',
          description='DeepSeek AI 分析接口')

# 模型定义
analyze_text_model = api.model('AnalyzeTextRequest', {
    'text': fields.String(required=True, description='待分析的文本内容'),
    'system_prompt': fields.String(required=False, description='DeepSeek 模型的系统提示词', default='你是一个专业的股票市场分析师。'),
    'stream_response': fields.Boolean(required=False, default=False, description='是否以流式方式返回响应')
})

# 新增：股票分析请求模型
analyze_stock_model = api.model('AnalyzeStockRequest', {
    'stock_code': fields.String(required=True, description='股票代码，例如 sh.600000'),
    'years_of_history': fields.Integer(required=False, default=3, description='分析的历史数据年限'),
    'stream_response': fields.Boolean(required=False, default=False, description='是否以流式方式返回响应')
})

# 新增：股票筛选请求模型
screen_stocks_model = api.model('ScreenStocksRequest', {
    'strategy_id': fields.Integer(required=False, description='根据特定策略筛选Top股票'),
    'top_n_stocks': fields.Integer(required=False, default=50, description='从Top策略股票中筛选的数量'),
    'min_win_rate': fields.Float(required=False, default=60.0, description='最低胜率要求 (例如: 60.0)'),
    'min_total_return': fields.Float(required=False, default=0.1, description='最低总收益率要求 (例如: 0.1)'),
    'stream_response': fields.Boolean(required=False, default=False, description='是否以流式方式返回响应')
})

# 新增：潜在股票分析结果模型
potential_stock_result_model = api.model('PotentialStockResult', {
    'stock_code': fields.String(description='股票代码'),
    'stock_name': fields.String(description='股票名称'),
    'potential_rating': fields.String(description='潜力评级 (高/中/低)'),
    'confidence_score': fields.Float(description='置信率 (0-100)'),
    'recommendation_reason': fields.String(description='推荐理由'),
    'buy_point': fields.String(description='建议买入点位'),
    'sell_point': fields.String(description='建议卖出点位'),
    'risks': fields.String(description='风险提示'),
})

@api.route('/analyze-text')
class AnalyzeTextResource(Resource):
    @api.expect(analyze_text_model)
    @api.doc(description='使用DeepSeek分析给定的文本内容，例如新闻或财报。')
    def post(self):
        """
        分析文本内容
        """
        data = api.payload
        text = data.get('text')
        system_prompt = data.get('system_prompt', '你是一个专业的股票市场分析师。')
        stream_response = data.get('stream_response', False)

        if not text:
            return api_error('文本内容不能为空', 400)

        try:
            # 从当前应用实例中获取 DeepSeekService
            deepseek_service = current_app.deepseek_service
            if not deepseek_service:
                raise RuntimeError("DeepSeekService 未初始化")

            if stream_response:
                # 收集完整的流式内容
                full_analysis_result = ""
                for chunk in deepseek_service.analyze_text(text, system_prompt, stream=True):
                    full_analysis_result += chunk
                analysis_result = full_analysis_result
            else:
                analysis_result = deepseek_service.analyze_text(text, system_prompt, stream=False)
            
            # 统一返回包含 prompt 和 analysis_result 的数据结构
            return api_success({
                'deepseek_prompt': text, # analyze-text 的 prompt 就是原始文本
                'analysis_result': analysis_result
            }, '文本分析成功')
        except ValueError as ve:
            return api_error(str(ve), 400)
        except Exception as e:
            current_app.logger.error(f"DeepSeek文本分析API调用失败: {e}")
            return api_error(f"文本分析失败: {e}", 500)

@api.route('/analyze-stock')
class AnalyzeStockResource(Resource):
    @api.expect(analyze_stock_model)
    @api.doc(description='结合历史数据和策略信号，使用DeepSeek分析股票走势和买卖点。')
    def post(self):
        """
        分析股票走势和买卖点
        """
        data = api.payload
        stock_code = data.get('stock_code')
        years_of_history = data.get('years_of_history', 3)
        stream_response = data.get('stream_response', False)

        if not stock_code:
            return api_error('股票代码不能为空', 400)

        try:
            stock = Stock.query.filter_by(code=stock_code).first()
            if not stock:
                return api_error('股票不存在', 404)

            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=years_of_history * 365) # 简单计算N年前的日期

            daily_data_records = DailyData.query.filter(
                DailyData.stock_id == stock.id,
                DailyData.trade_date >= start_date,
                DailyData.trade_date <= end_date
            ).order_by(DailyData.trade_date).all()

            if not daily_data_records:
                return api_error('未找到足够的历史数据进行分析', 404)

            # 将数据转换为 Pandas DataFrame
            df = pd.DataFrame([d.to_dict() for d in daily_data_records])
            # 确保 trade_date 是 datetime 对象，并设置为索引
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.set_index('trade_date').sort_index()

            # 运行策略并收集信号
            strategies = {
                "RSI策略": RsiStrategy(),
                "MACD策略": MacdStrategy(),
                "双均线策略": DualMovingAverageStrategy()
            }
            
            strategy_signals = {}
            for name, strategy_instance in strategies.items():
                # 在传递给策略之前，将 trade_date 从索引重置为列
                signals_df = strategy_instance.generate_signals(df.reset_index().copy())
                # 提取最近的信号
                latest_signal = signals_df['signal'].iloc[-1] if not signals_df.empty else "无信号"
                strategy_signals[name] = latest_signal
            
            # 构建 DeepSeek 的提示词
            prompt_parts = []
            prompt_parts.append(f"请作为专业的股票市场分析师，结合以下信息对股票 {stock.name} ({stock.code}) 的未来走势和可能操作的买卖点进行详细分析：\n")
            prompt_parts.append(f"\n--- 股票基础信息 ---\n")
            prompt_parts.append(f"名称: {stock.name}\n")
            prompt_parts.append(f"代码: {stock.code}\n")
            prompt_parts.append(f"行业: {stock.industry}\n")
            prompt_parts.append(f"市场: {stock.market}\n")

            prompt_parts.append(f"\n--- 最近历史行情摘要 (最近10个交易日) ---\n")
            recent_data = df.tail(10)
            for _, row in recent_data.iterrows():
                prompt_parts.append(f"日期: {row.name.strftime('%Y-%m-%d')}, 收盘价: {row['close_price']:.2f}, 成交量: {row['volume']}\n")

            prompt_parts.append(f"\n--- 策略分析信号 ---\n")
            for name, signal in strategy_signals.items():
                prompt_parts.append(f"{name}: 当前信号为 '{signal}'.\n")
            
            prompt_parts.append(f"\n--- 分析要求 ---\n")
            prompt_parts.append(f"请综合以上信息，判断该股票未来可能的短期、中期走势，并给出明确的买入点位和卖出点位建议，说明您的推理过程和依据。同时，请指出潜在的风险因素。\n")
            prompt_parts.append(f"请以结构化的方式返回分析结果，例如：\n")
            prompt_parts.append(f"未来走势预测: ...\n")
            prompt_parts.append(f"建议买入点位: ...\n")
            prompt_parts.append(f"建议卖出点位: ...\n")
            prompt_parts.append(f"分析依据: ...\n")
            prompt_parts.append(f"风险提示: ...\n")
            
            deepseek_prompt = "".join(prompt_parts)
            
            deepseek_service = current_app.deepseek_service
            if not deepseek_service:
                raise RuntimeError("DeepSeekService 未初始化")

            if stream_response:
                # 收集完整的流式内容
                full_analysis_result = ""
                for chunk in deepseek_service.analyze_text(deepseek_prompt, stream=True):
                    full_analysis_result += chunk
                analysis_result = full_analysis_result
            else:
                analysis_result = deepseek_service.analyze_text(deepseek_prompt, stream=False)
            
            # 统一返回包含 prompt 和 analysis_result 的数据结构
            return api_success({
                'deepseek_prompt': deepseek_prompt,
                'analysis_result': analysis_result
            }, '股票分析成功')
        except ValueError as ve:
            return api_error(str(ve), 400)
        except Exception as e:
            current_app.logger.error(f"DeepSeek股票分析API调用失败: {e}")
            return api_error(f"股票分析失败: {e}", 500)

def _analyze_top_stocks_with_deepseek(app, candidate_top_stocks: list[TopStrategyStock]):
    """
    内部函数：根据给定的TopStrategyStock列表，调用DeepSeek进行批量分析。
    参数:
        app: Flask应用实例，用于获取deepseek_service和logger。
        candidate_top_stocks: TopStrategyStock对象的列表。
    返回:
        list[dict]: DeepSeek分析后的推荐股票列表，或抛出异常。
    """
    # 用于收集 DeepSeek 期望的每只股票的输入数据 (analysis 部分)
    deepseek_input_stocks_data = []

    with app.app_context(): # 确保在应用上下文中运行
        for top_stock in candidate_top_stocks:
            stock = Stock.query.filter_by(code=top_stock.stock_code).first()
            if not stock:
                app.logger.warning(f"股票 {top_stock.stock_code} 的基础信息不存在，跳过AI分析。")
                continue 
            
            # 获取最近的日线数据 (例如最近90天)
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=90) 
            daily_data_records = DailyData.query.filter(
                DailyData.stock_id == stock.id,
                DailyData.trade_date >= start_date,
                DailyData.trade_date <= end_date
            ).order_by(DailyData.trade_date).all()

            df = pd.DataFrame([d.to_dict() for d in daily_data_records])
            if df.empty:
                app.logger.warning(f"股票 {top_stock.stock_code} 未找到足够的历史数据进行AI分析，跳过。")
                continue
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.set_index('trade_date').sort_index()

            # 运行策略并收集信号
            strategies_instances = {
                "RSI策略": RsiStrategy(),
                "MACD策略": MacdStrategy(),
                "双均线策略": DualMovingAverageStrategy()
            }
            strategy_signals = {}
            for name, strategy_instance in strategies_instances.items():
                signals_df = strategy_instance.generate_signals(df.reset_index().copy())
                latest_signal = signals_df['signal'].iloc[-1] if not signals_df.empty else "无信号"
                strategy_signals[name] = latest_signal
            
            # 构建每只股票的详细摘要，作为 'analysis' 字段的内容
            stock_analysis_text = f"### 股票: {stock.name} ({stock.code})\n"
            stock_analysis_text += f"行业: {stock.industry}, 市场: {stock.market}\n"
            stock_analysis_text += f"回测胜率: {top_stock.win_rate:.2f}%, 总收益: {top_stock.total_return:.2f}%, 最大回撤: {top_stock.max_drawdown:.2f}%\n"
            if not df.empty:
                stock_analysis_text += f"最近收盘价: {df['close_price'].iloc[-1]:.2f}, 最近成交量: {df['volume'].iloc[-1]}\n"
            else:
                stock_analysis_text += "无近期行情数据。\n"

            for s_name, s_signal in strategy_signals.items():
                stock_analysis_text += f"{s_name}信号: {s_signal}\n"
            
            deepseek_input_stocks_data.append({
                "stock_code": stock.code,
                "stock_name": stock.name,
                "analysis": stock_analysis_text 
            })

        # Construct the user message (final_deepseek_prompt)
        prompt_intro = """请作为专业的股票市场分析师，根据以下提供的股票回测表现、最近行情和策略信号，\n对每只股票的未来潜力、短期中期走势、置信率以及建议的买卖点进行详细分析。\n同时，请指出潜在的风险因素。\n\n以下是需要分析的股票数据，以JSON格式提供：\n```json\n"""
        json_input_for_deepseek = json.dumps(deepseek_input_stocks_data, indent=2, ensure_ascii=False)
        prompt_outro = """\n```\n"""
        final_deepseek_prompt = prompt_intro + json_input_for_deepseek + prompt_outro

        # Define the system prompt for DeepSeek
        system_prompt_for_deepseek = """你是一个专业的股票市场分析师。请严格按照以下JSON数组格式输出你的分析结果，不要包含任何额外文字或解释：\n[\n  {\n    \"stock_code\": \"股票代码\",\n    \"stock_name\": \"股票名称\",\n    \"potential_rating\": \"潜力评级 (高/中/低)\",\n    \"confidence_score\": \"置信率 (0-100的数字)\",\n    \"recommendation_reason\": \"推荐理由\",\n    \"buy_point\": \"建议买入点位\",\n    \"sell_point\": \"建议卖出点位\",\n    \"risks\": \"风险提示\"\n  },\n  // ... 其他股票的分析结果\n]\n"""

        # 调用 DeepSeek 服务
        deepseek_service = app.deepseek_service
        if not deepseek_service:
            raise RuntimeError("DeepSeekService 未初始化")

        analysis_results_json_str = deepseek_service.analyze_text(
            final_deepseek_prompt,
            system_prompt=system_prompt_for_deepseek,
            stream=False
        )
        
        # 尝试解析DeepSeek的JSON响应
        try:
            # 提取JSON块，可能被Markdown代码块包裹
            if analysis_results_json_str.strip().startswith('```json') and analysis_results_json_str.strip().endswith('```'):
                json_str = analysis_results_json_str.strip()[len('```json'):-len('```')].strip()
            else:
                json_str = analysis_results_json_str.strip()
            
            deepseek_recommendations = json.loads(json_str)

            # Validate the structure of the returned JSON against potential_stock_result_model
            for item in deepseek_recommendations:
                required_keys = ['stock_code', 'stock_name', 'potential_rating', 'confidence_score',
                                 'recommendation_reason', 'buy_point', 'sell_point', 'risks']
                if not all(k in item for k in required_keys):
                    raise ValueError(f"DeepSeek返回的JSON结构不符合预期，缺少关键字段。缺失字段：{[k for k in required_keys if k not in item]}")
                
                # 尝试将 confidence_score 转换为浮点数
                if 'confidence_score' in item:
                    try:
                        item['confidence_score'] = float(item['confidence_score'])
                    except (ValueError, TypeError):
                        raise ValueError(f"置信率 (confidence_score) 格式错误: {item.get('confidence_score')}")
                else:
                    raise ValueError("DeepSeek返回的JSON中缺少 'confidence_score' 字段。")

        except json.JSONDecodeError as e:
            app.logger.error(f"解析DeepSeek JSON响应失败: {e}, 原始响应: {analysis_results_json_str}")
            raise ValueError(f"AI分析结果解析失败: {e}") # Re-raise as ValueError for consistent error handling
        except ValueError as e:
            app.logger.error(f"DeepSeek返回的JSON内容验证失败: {e}, 原始响应: {analysis_results_json_str}")
            raise ValueError(f"AI分析结果内容验证失败: {e}") # Re-raise as ValueError

    return deepseek_recommendations

@api.route('/screen-potential-stocks')
class ScreenPotentialStocksResource(Resource):
    @api.expect(screen_stocks_model)
    @api.doc(description='从历史回测数据中筛选潜力股票，并使用DeepSeek进行深度分析和推荐。')
    def post(self):
        """
        筛选潜力股票并获取AI分析推荐
        """
        data = api.payload
        strategy_id = data.get('strategy_id')
        top_n_stocks = data.get('top_n_stocks', 50)
        min_win_rate = data.get('min_win_rate', 60.0)
        min_total_return = data.get('min_total_return', 0.1)
        # stream_response = data.get('stream_response', False) # This is handled by _analyze_top_stocks_with_deepseek internally as False

        try:
            query = TopStrategyStock.query
            if strategy_id:
                query = query.filter_by(strategy_id=strategy_id)

            # 应用筛选条件
            query = query.filter(
                TopStrategyStock.win_rate >= min_win_rate,
                TopStrategyStock.total_return >= min_total_return
            )

            # 排序并限制数量
            candidate_top_stocks = query.order_by(TopStrategyStock.win_rate.desc(), TopStrategyStock.total_return.desc())
            
            # 防止一次性查询过多，限制在最多top_n_stocks+100，避免数据库压力过大
            candidate_top_stocks = candidate_top_stocks.limit(top_n_stocks + 100).all()

            if not candidate_top_stocks:
                return api_error('未找到符合筛选条件的潜力股票', 404)

            # 调用新的内部函数进行DeepSeek分析
            deepseek_recommendations = _analyze_top_stocks_with_deepseek(current_app, candidate_top_stocks)
            
            # 返回最终结果
            return api_success({
                'recommended_stocks': deepseek_recommendations
            }, '潜力股票分析推荐成功')
        
        except ValueError as ve:
            return api_error(str(ve), 400)
        except Exception as e:
            current_app.logger.error(f"DeepSeek潜力股票分析API调用失败: {e}")
            return api_error(f"潜力股票分析失败: {e}", 500) 