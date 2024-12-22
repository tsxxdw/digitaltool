from flask import Flask
from logic import index_logic, action_logic, train_logic, sync_logic

app = Flask(__name__)

# 注册蓝图
app.register_blueprint(index_logic.bp)
app.register_blueprint(action_logic.bp)
app.register_blueprint(train_logic.bp)
app.register_blueprint(sync_logic.bp)

if __name__ == '__main__':
    app.run(debug=True) 