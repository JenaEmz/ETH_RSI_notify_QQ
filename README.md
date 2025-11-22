 方案一：使用 xzhouqd/qsign 镜像
这是目前社区中非常流行且相对简单的一个选择
。
拉取Docker镜像
在你的服务器上执行以下命令来获取镜像：
docker pull xzhouqd/qsign:8.9.63
运行签名服务器容器
使用下面的命令启动一个容器。关键的一步是设置 ANDROID_ID环境变量。这个ID需要与你的机器人框架（如Lagrange或go-cqhttp）配置文件（通常是device.json）中的 android_id值保持一致
。
docker run -d --restart=always --name qsign -p 8080:8080 -e ANDROID_ID=6a0d015c82f83971 xzhouqd/qsign:8.9.63
