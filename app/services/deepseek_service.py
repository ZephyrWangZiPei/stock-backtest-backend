import os
from openai import OpenAI
# from flask import current_app # 移除对 current_app 的导入

class DeepSeekService:
    def __init__(self, api_key: str):
        # 从 Flask 应用配置中获取 DeepSeek API Key
        # 确保在 config.py 中配置 DEEPSEEK_API_KEY
        # api_key = current_app.config.get('DEEPSEEK_API_KEY') # 移除此行
        if not api_key:
            raise ValueError("DeepSeek API Key 未提供。")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
        )
        self.model = "deepseek-chat" # 更新为正确的模型名称

    def analyze_text(self, text: str, system_prompt: str = "你是一个专业的股票市场分析师。", stream: bool = False):
        """
        使用 DeepSeek-V3 模型分析文本，例如新闻、财报内容。
        :param stream: 如果为True，则以流式方式返回结果。
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7, # 控制生成文本的随机性
                max_tokens=2048, # 限制最大输出长度
                stream=stream    # 控制是否流式输出
            )
            
            if stream:
                def generate():
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                return generate()
            else:
                return response.choices[0].message.content
        except Exception as e:
            # current_app.logger.error(f"DeepSeek API 调用失败: {e}") # 移除对 current_app 的直接引用
            # return f"DeepSeek 分析失败: {e}"
            raise # 重新抛出异常，让调用方处理日志和错误响应

    # 未来可以添加更多方法，例如：
    # def analyze_structured_data(self, data: dict):
    #     """分析结构化数据，如历史行情或财务数据。"""
    #     pass

    # def generate_trading_points(self, stock_data: dict, news_summary: str):
    #     """结合多维度信息，生成建议的交易点位。"""
    #     pass 