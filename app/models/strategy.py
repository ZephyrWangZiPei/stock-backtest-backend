from app import db
from datetime import datetime
import json
import ast

class Strategy(db.Model):
    """策略定义表"""
    __tablename__ = 'strategies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, comment='策略名称')
    description = db.Column(db.Text, comment='策略描述')
    
    # 参数以JSON格式存储，方便扩展
    # 例如：{"short_window": 5, "long_window": 20}
    parameters = db.Column(db.Text, nullable=False, comment='策略参数 (JSON格式)')
    
    # 策略的唯一标识符，用于代码中调用
    # 例如：'dual_moving_average'
    identifier = db.Column(db.String(50), unique=True, nullable=False, index=True, comment='策略代码标识符')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_parameters(self, params: dict):
        self.parameters = json.dumps(params)

    def get_parameters(self):
        """安全地解析参数JSON字符串"""
        if not self.parameters:
            return {}
        try:
            # 使用 literal_eval 更安全地处理可能不严格的 "JSON"
            return ast.literal_eval(self.parameters)
        except (ValueError, SyntaxError):
            # 如果解析失败，返回空字典
            return {}

    def __repr__(self):
        return f'<Strategy {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'parameters': self.get_parameters(),
            'identifier': self.identifier,
            'created_at': self.created_at.isoformat()
        } 