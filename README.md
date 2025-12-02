# 1. 更新软件包列表
sudo apt update

# 2. 升级已安装的包（可选，但推荐）
sudo apt upgrade -y

# 3. 安装编译工具和Python环境依赖
sudo apt install -y python3 python3-pip python3-venv wget

python3 -m venv venv

# 2. 激活虚拟环境
source venv/bin/activate
pip install requests
pip install pandas  
pip install numpy
pip install apscheduler
pip install matplotlib
nohup python3 -u eth_robot_wt.py 
ps aux | grep eth_robot_wt.py &
