拉取Docker镜像
在你的服务器上执行以下命令来获取镜像：
docker pull xzhouqd/qsign:8.9.63
运行签名服务器容器
使用下面的命令启动一个容器。关键的一步是设置 ANDROID_ID环境变量。这个ID需要与你的机器人框架（如Lagrange或go-cqhttp）配置文件（通常是device.json）中的 android_id值保持一致
。
docker run -d \
  --restart=always \
  --name qsign \
  -p 8080:8080 \  # 将容器内8080端口映射到服务器8080端口
  -e ANDROID_ID=这里替换成你的android_id \  # 务必修改！
  xzhouqd/qsign:8.9.63
