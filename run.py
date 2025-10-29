import os
from app import app

if __name__ == '__main__':
    # 根据环境变量决定是否启用debug模式
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    # 获取端口号，默认为5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=debug, port=port)
