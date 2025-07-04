from flask import Blueprint, current_app, request, jsonify
from flask_socketio import emit
from app import socketio, db
from app.models import BacktestResult, Strategy, Stock, DailyData
import logging
from datetime import datetime, timedelta
import json
import pandas as pd

logger = logging.getLogger(__name__)

def init_ai_analysis_ws(app):
    """初始化 AI 分析 WebSocket 事件处理器。"""
    socketio_instance = socketio  # 取全局实例

    NAMESPACE = '/ai_analysis'

    @socketio_instance.on('connect', namespace=NAMESPACE)
    def handle_connect():
        sid = request.sid
        logger.info(f"AI分析客户端 {sid} 已连接")

    @socketio_instance.on('start_ai_analysis', namespace=NAMESPACE)
    def handle_start_ai_analysis(data):
        """前端请求开始 AI 分析。
        期望 data 至少包含 backtest_id。
        """
        sid = request.sid
        backtest_id = data.get('backtest_id') if isinstance(data, dict) else None
        if not backtest_id:
            emit('ai_analysis_error', {'message': '缺少 backtest_id'}, room=sid, namespace=NAMESPACE)
            return

        # 启动后台任务，避免阻塞 SocketIO 线程
        socketio_instance.start_background_task(ai_analysis_task, sid, backtest_id)

    def ai_analysis_task(sid: str, backtest_id: int):
        """执行 AI 分析、流式推送结果并保存到数据库。"""
        logger.info(f"开始为回测 {backtest_id} 执行 AI 分析 (sid={sid})")
        try:
            with app.app_context():
                # 1. 获取回测结果及相关信息
                result: BacktestResult = BacktestResult.query.get(backtest_id)
                if not result or result.status != 'completed':
                    socketio_instance.emit('ai_analysis_error', {'message': '回测结果不存在或未完成'}, room=sid, namespace=NAMESPACE)
                    return

                # 如果已存在 AI 分析报告，直接推送
                if result.ai_analysis_report:
                    logger.info(f"回测 {backtest_id} 已存在AI分析报告，直接推送。")
                    # 为模拟流式效果，也可以分块推送，这里直接一次性推送
                    socketio_instance.emit('ai_analysis_chunk', {'content': result.ai_analysis_report}, room=sid, namespace=NAMESPACE)
                    socketio_instance.emit('ai_analysis_complete', {'message': '分析完成 (来自缓存)'}, room=sid, namespace=NAMESPACE)
                    return

                strategy: Strategy | None = Strategy.query.get(result.strategy_id)
                # 2. 获取最新股票数据
                latest_data_list = _fetch_latest_stock_data(result.get_selected_stocks())

                # 3. 构建 Prompt
                prompt = _build_ai_prompt(result, strategy, latest_data_list)

                deepseek_service = app.deepseek_service
                if not deepseek_service:
                    raise RuntimeError("DeepSeekService 未初始化")

                # 4. 调用 DeepSeek (流式)
                chunk_generator = deepseek_service.analyze_text(prompt, stream=True)
                full_report = ""
                for chunk in chunk_generator:
                    full_report += chunk
                    # 实时推送给前端
                    socketio_instance.emit('ai_analysis_chunk', {'content': chunk}, room=sid, namespace=NAMESPACE)

                # 5. 推送完成事件
                socketio_instance.emit('ai_analysis_complete', {'message': '分析完成'}, room=sid, namespace=NAMESPACE)

                # 6. 保存完整报告到数据库
                result.ai_analysis_report = full_report
                db.session.commit()
                logger.info(f"AI 分析结果已保存到回测 {backtest_id}")
        except Exception as e:
            logger.error(f"AI 分析任务失败: {e}", exc_info=True)
            socketio_instance.emit('ai_analysis_error', {'message': str(e)}, room=sid, namespace=NAMESPACE)

    def _fetch_latest_stock_data(stock_codes: list[str]):
        """获取每只股票最新一个交易日的行情数据 & 简易技术指标。"""
        data_list = []
        try:
            for code in stock_codes:
                stock = Stock.query.filter_by(code=code).first()
                if not stock:
                    continue
                daily: DailyData | None = DailyData.query.filter_by(stock_id=stock.id).order_by(DailyData.trade_date.desc()).first()
                if not daily:
                    continue
                # 这里仅返回基础数据，技术指标简单计算或留空
                item = {
                    'stock_code': code,
                    'latest_date': daily.trade_date.isoformat(),
                    'open_price': daily.open_price,
                    'high_price': daily.high_price,
                    'low_price': daily.low_price,
                    'close_price': daily.close_price,
                    'volume': daily.volume,
                    'technical_indicators': {
                        # 占位，可扩展
                    },
                    'recent_news_summary': ''  # TODO: 可调用新闻API
                }
                data_list.append(item)
        except Exception as e:
            logger.error(f"获取最新股票数据失败: {e}", exc_info=True)
        return data_list

    def _build_ai_prompt(result: BacktestResult, strategy: Strategy | None, latest_data: list):
        """根据此前确定的模板构建Prompt。此处仅实现最核心字段，可按需扩展。"""
        # 基础信息
        prompt_parts = []
        prompt_parts.append("你是一个专业的量化投资策略分析师，你的任务是根据以下提供的回测结果、详细策略规则、交易日志和最新股票市场数据，生成一份详细、专业、客观且具有实操指导意义的AI分析报告。\n")
        prompt_parts.append("请你不仅仅是总结数据，更要深入挖掘数据背后的原因和含义，提供前瞻性的、可操作的优化建议和风险规避方案。特别重要的是，请结合最新市场数据，对未来最近一个交易日的买卖点位给出具体、量化的推荐，并详细阐述推荐理由。\n\n")

        # 策略信息
        prompt_parts.append("--- 策略基本信息 ---\n")
        if strategy:
            prompt_parts.append(f"策略名称: {strategy.name}\n")
            prompt_parts.append(f"策略标识符: {strategy.identifier}\n")
            prompt_parts.append(f"策略描述: {strategy.description or '无描述'}\n")
            # TODO: 您需要在Strategy模型中增加一个字段来存储详细的策略规则，例如 strategy.rules_detail
            # 目前暂时使用 description 作为占位符，但AI的分析深度将受限于此
            prompt_parts.append(f"策略交易规则详情:\n```json\n{strategy.description or '此处应为详细的策略规则描述或JSON'}\n```\n")
            prompt_parts.append("（请详细解读上述策略规则，并评估其逻辑严谨性与市场适应性。）\n\n")

        # 关键指标
        prompt_parts.append("--- 回测关键指标概览 ---\n")
        prompt_parts.append(f"总回报率: {float(result.total_return) * 100 if result.total_return is not None else 'N/A'}%\n")
        prompt_parts.append(f"年化回报率: {float(result.annual_return) * 100 if result.annual_return is not None else 'N/A'}%\n")
        prompt_parts.append(f"最大回撤: {float(result.max_drawdown) * 100 if result.max_drawdown is not None else 'N/A'}%\n")
        prompt_parts.append(f"夏普比率: {float(result.sharpe_ratio) if result.sharpe_ratio is not None else 'N/A'}\n")
        prompt_parts.append(f"胜率: {float(result.win_rate) * 100 if result.win_rate is not None else 'N/A'}%\n")
        # 假设以下字段已在BacktestResult中存在或可计算
        prompt_parts.append(f"盈亏比 (平均盈利/平均亏损): {float(result.profit_loss_ratio) if hasattr(result, 'profit_loss_ratio') and result.profit_loss_ratio is not None else 'N/A'}\n")
        prompt_parts.append(f"平均每笔盈利: {float(result.avg_profit_per_trade) * 100 if hasattr(result, 'avg_profit_per_trade') and result.avg_profit_per_trade is not None else 'N/A'}%\n")
        prompt_parts.append(f"平均每笔亏损: {float(result.avg_loss_per_trade) * 100 if hasattr(result, 'avg_loss_per_trade') and result.avg_loss_per_trade is not None else 'N/A'}%\n")
        prompt_parts.append(f"最大连续盈利次数: {result.max_consecutive_wins if hasattr(result, 'max_consecutive_wins') and result.max_consecutive_wins is not None else 'N/A'}\n")
        prompt_parts.append(f"最大连续亏损次数: {result.max_consecutive_losses if hasattr(result, 'max_consecutive_losses') and result.max_consecutive_losses is not None else 'N/A'}\n")
        prompt_parts.append(f"平均持仓天数: {result.avg_holding_days if hasattr(result, 'avg_holding_days') and result.avg_holding_days is not None else 'N/A'}\n")
        prompt_parts.append("\n")

        # 资金曲线数据
        if result.portfolio_history:
            prompt_parts.append("--- 资金曲线数据 ---\n")
            prompt_parts.append(f"```json\n{result.portfolio_history}\n```\n") # 假设portfolio_history已经是JSON字符串
            prompt_parts.append("（请结合资金曲线的形态，分析策略在不同市场阶段（如上涨、下跌、震荡市）的表现，并指出资金曲线的风险点，例如长期停滞或加速下跌的区间。）\n\n")

        # 详细交易日志
        # 假设 result.trades 是一个包含交易记录的列表，需要序列化为 JSON
        if result.trades:
            prompt_parts.append("--- 详细交易日志 ---\n")
            prompt_parts.append("（以下是策略执行的每一笔交易的详细记录。请深入分析每笔盈利和亏损交易的具体原因，特别关注亏损交易，找出其共性特征或触发原因，以便为策略优化提供依据。）\n")
            # 假设 result.trades 可以直接被 json.dumps 序列化，或者需要先转换为 dict 列表
            try:
                # 尝试将 BacktestTrade 对象转换为字典列表
                trade_logs_as_dict = [trade.to_dict() if hasattr(trade, 'to_dict') else trade for trade in result.trades]
                prompt_parts.append(f"```json\n{json.dumps(trade_logs_as_dict, ensure_ascii=False, indent=2)}\n```\n\n")
            except Exception:
                # 如果序列化失败，退回到原始字符串，或者提示需要转换
                prompt_parts.append(f"```json\n{json.dumps(result.trades, ensure_ascii=False, indent=2)}\n```\n\n")
        else:
            prompt_parts.append("--- 详细交易日志 ---\n")
            prompt_parts.append("无详细交易日志可供分析。\n\n")


        # 最新数据
        prompt_parts.append("--- 最新股票市场数据及技术指标 ---\n")
        prompt_parts.append("（这份数据是指定股票最新的OHLCV和所有已计算的技术指标，是您进行未来交易点位预测和分析的依据。）\n")
        prompt_parts.append(json.dumps(latest_data, ensure_ascii=False, indent=2))
        prompt_parts.append("\n\n")

        prompt_parts.append("--- 分析报告结构与内容要求 ---\n")
        prompt_parts.append("请严格按照以下结构、内容和**格式要求**，生成一份专业、有深度且**易于阅读**的分析报告：\n\n")
        prompt_parts.append("**格式要求：**\n")
        prompt_parts.append("  - **报告概述**: 在报告的开头提供一个简洁的概述，快速总结策略表现、关键发现和最核心的优化建议。\n")
        prompt_parts.append("  - **标题层级**: 主要章节使用二级标题（`## 章节名称`），子节使用三级标题（`### 子节名称`），四级标题使用（`#### 具体内容`）。\n")
        prompt_parts.append("  - **表格使用**: 对于关键指标对比、交易统计、风险分析等数据，请使用Markdown表格格式呈现，确保数据清晰可读。\n")
        prompt_parts.append("  - **内容组织**: 使用列表（无序或有序）、表格、引用块等结构化方式呈现关键数据和要点。每个段落控制在3-5句话内，避免冗长段落。每个主要章节结束后提供一个简短的总结。\n")
        prompt_parts.append("  - **关键信息**: 重要的结论、发现、优势、劣势或建议请使用**粗体**突出显示。\n")
        prompt_parts.append("  - **数据引用**: 对于引用原始数据（如资金曲线、交易日志、最新股票数据），请使用Markdown代码块（```json...```）进行格式化，并在其后进行**简洁的总结和解读**，而不是简单罗列。\n")
        prompt_parts.append("  - **语言风格**: 报告应使用专业、客观、清晰且简洁的中文进行撰写。\n")
        prompt_parts.append("  - **逻辑流畅性与重点突出**: 确保报告内容逻辑连贯，从宏观到微观，从分析到建议，层层递进。在每个部分，清晰地表达核心观点，避免含糊不清。\n")
        prompt_parts.append("  - **可操作性**: 所有建议都应具体、量化且具备可操作性，避免宽泛的建议。\n\n")

        prompt_parts.append("**报告结构：**\n\n")
        prompt_parts.append("## 📊 报告概述\n")
        prompt_parts.append("### 策略表现概览\n")
        prompt_parts.append("请使用表格形式展示关键指标：\n")
        prompt_parts.append("| 指标 | 数值 | 评价 |\n")
        prompt_parts.append("|------|------|------|\n")
        prompt_parts.append("| 总回报率 | XX% | 优秀/良好/一般/较差 |\n")
        prompt_parts.append("| 年化回报率 | XX% | 优秀/良好/一般/较差 |\n")
        prompt_parts.append("| 最大回撤 | XX% | 优秀/良好/一般/较差 |\n")
        prompt_parts.append("| 夏普比率 | XX | 优秀/良好/一般/较差 |\n")
        prompt_parts.append("| 胜率 | XX% | 优秀/良好/一般/较差 |\n\n")
        prompt_parts.append("### 核心发现与建议\n")
        prompt_parts.append("- **主要优势**: [列出2-3个核心优势]\n")
        prompt_parts.append("- **主要风险**: [列出2-3个主要风险点]\n")
        prompt_parts.append("- **优化建议**: [列出2-3个最重要的优化方向]\n\n")

        prompt_parts.append("## 🔍 策略整体表现评估\n")
        prompt_parts.append("### 宏观表现分析\n")
        prompt_parts.append("#### 盈利能力评估\n")
        prompt_parts.append("#### 风险控制能力\n")
        prompt_parts.append("#### 策略稳定性分析\n\n")

        prompt_parts.append("## 📈 关键指标深度解析\n")
        prompt_parts.append("### 回报与风险平衡分析\n")
        prompt_parts.append("请使用表格对比不同指标：\n")
        prompt_parts.append("| 风险指标 | 数值 | 行业标准 | 评价 |\n")
        prompt_parts.append("|----------|------|----------|------|\n")
        prompt_parts.append("| 夏普比率 | XX | >1.0 | 优秀/良好/一般/较差 |\n")
        prompt_parts.append("| 最大回撤 | XX% | <20% | 优秀/良好/一般/较差 |\n")
        prompt_parts.append("| 波动率 | XX% | - | 优秀/良好/一般/较差 |\n\n")
        prompt_parts.append("### 交易效率分析\n")
        prompt_parts.append("#### 胜率与盈亏比分析\n")
        prompt_parts.append("#### 交易频率与持仓时间\n")
        prompt_parts.append("#### 连续盈亏分析\n\n")

        prompt_parts.append("## ⚡ 策略优势与劣势剖析\n")
        prompt_parts.append("### 策略优势\n")
        prompt_parts.append("#### 市场适应性优势\n")
        prompt_parts.append("#### 交易逻辑优势\n")
        prompt_parts.append("#### 风险控制优势\n\n")
        prompt_parts.append("### 策略劣势\n")
        prompt_parts.append("#### 市场环境限制\n")
        prompt_parts.append("#### 交易逻辑缺陷\n")
        prompt_parts.append("#### 风险控制不足\n\n")

        prompt_parts.append("## ⚠️ 潜在风险点识别与规避建议\n")
        prompt_parts.append("### 市场风险分析\n")
        prompt_parts.append("| 风险类型 | 风险程度 | 影响分析 | 规避建议 |\n")
        prompt_parts.append("|----------|----------|----------|----------|\n")
        prompt_parts.append("| 流动性风险 | 高/中/低 | [具体分析] | [具体建议] |\n")
        prompt_parts.append("| 政策风险 | 高/中/低 | [具体分析] | [具体建议] |\n")
        prompt_parts.append("| 行业风险 | 高/中/低 | [具体分析] | [具体建议] |\n\n")
        prompt_parts.append("### 策略固有风险\n")
        prompt_parts.append("#### 止损失效风险\n")
        prompt_parts.append("#### 过度交易风险\n")
        prompt_parts.append("#### 信号滞后风险\n\n")
        prompt_parts.append("### 连续亏损分析\n")
        prompt_parts.append("#### 亏损模式识别\n")
        prompt_parts.append("#### 应对方案建议\n\n")

        prompt_parts.append("## 🛠️ 策略优化方向与具体改进建议\n")
        prompt_parts.append("### 基于交易日志的优化建议\n")
        prompt_parts.append("#### 买入信号优化\n")
        prompt_parts.append("#### 卖出信号优化\n")
        prompt_parts.append("#### 止损止盈优化\n")
        prompt_parts.append("#### 持仓时间优化\n\n")
        prompt_parts.append("### 参数调整建议\n")
        prompt_parts.append("| 参数名称 | 当前值 | 建议值 | 调整理由 |\n")
        prompt_parts.append("|----------|--------|--------|----------|\n")
        prompt_parts.append("| [参数1] | [当前值] | [建议值] | [调整理由] |\n")
        prompt_parts.append("| [参数2] | [当前值] | [建议值] | [调整理由] |\n\n")
        prompt_parts.append("### 稳健性增强建议\n")
        prompt_parts.append("#### 技术指标补充\n")
        prompt_parts.append("#### 基本面因子引入\n")
        prompt_parts.append("#### 多策略组合\n\n")

        prompt_parts.append("## 🎯 未来交易预测与操作建议\n")
        prompt_parts.append("### 市场环境分析\n")
        prompt_parts.append("#### 当前市场状态\n")
        prompt_parts.append("#### 技术面分析\n")
        prompt_parts.append("#### 基本面分析\n\n")
        prompt_parts.append("### 精确买卖点推荐\n")
        prompt_parts.append("#### 买入点位建议\n")
        prompt_parts.append("**推荐买入价格区间**: [具体价格区间]\n")
        prompt_parts.append("**买入触发条件**: [具体条件]\n")
        prompt_parts.append("**推荐理由**: [技术分析依据]\n\n")
        prompt_parts.append("#### 卖出点位建议\n")
        prompt_parts.append("**推荐卖出价格区间**: [具体价格区间]\n")
        prompt_parts.append("**卖出触发条件**: [具体条件]\n")
        prompt_parts.append("**推荐理由**: [技术分析依据]\n\n")
        prompt_parts.append("### 风险提示与注意事项\n")
        prompt_parts.append("- **市场风险**: [具体风险提示]\n")
        prompt_parts.append("- **操作风险**: [具体风险提示]\n")
        prompt_parts.append("- **注意事项**: [具体注意事项]\n\n")

        prompt_parts.append("## 📊 多维度表现分析\n")
        prompt_parts.append("### 按时间周期分析\n")
        prompt_parts.append("#### 月度表现分析\n")
        prompt_parts.append("| 月份 | 回报率 | 回撤 | 胜率 | 交易次数 |\n")
        prompt_parts.append("|------|--------|------|------|----------|\n")
        prompt_parts.append("| [月份] | [回报率] | [回撤] | [胜率] | [交易次数] |\n\n")
        prompt_parts.append("#### 季度表现分析\n")
        prompt_parts.append("#### 年度表现分析\n\n")
        prompt_parts.append("### 按市场环境分析\n")
        prompt_parts.append("#### 牛市表现\n")
        prompt_parts.append("#### 熊市表现\n")
        prompt_parts.append("#### 震荡市表现\n")
        prompt_parts.append("#### 趋势市表现\n\n")
        prompt_parts.append("### 按股票特性分析\n")
        prompt_parts.append("#### 行业板块表现\n")
        prompt_parts.append("| 行业 | 回报率 | 胜率 | 交易次数 | 表现评价 |\n")
        prompt_parts.append("|------|--------|------|----------|----------|\n")
        prompt_parts.append("| [行业] | [回报率] | [胜率] | [交易次数] | [评价] |\n\n")
        prompt_parts.append("#### 市值规模表现\n")
        prompt_parts.append("#### 股票特性总结\n\n")

        prompt_parts.append("## 📋 总结与建议\n")
        prompt_parts.append("### 策略综合评价\n")
        prompt_parts.append("### 核心优化建议\n")
        prompt_parts.append("### 风险控制要点\n")
        prompt_parts.append("### 未来发展方向\n\n")

        prompt_parts.append("请严格按照以上结构和格式要求生成报告，确保内容专业、结构清晰、易于阅读。\n")

        return "".join(prompt_parts)

    return None  # init 函数不需要返回值 