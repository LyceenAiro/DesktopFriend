## 这是一个桌宠
### 目前开发进度
#### 1. 框架搭建
- [x] 注册表框架
- [x] 基础的画面显示框架  
- [x] 拖动行为  
- [x] 右键功能列表  
- [x] 在最顶层功能  
- [x] 小图标功能列表  
- [x] 最小化图标隐藏  
- [x] 桌宠行走功能  
- [x] 补全动作图像  
- [x] github库发布  
#### 2. 更多基础功能
- [x] 进入推出渐入动画
- [x] 资源文件编码
- [x] 项目打包
- [x] 资源包格式加载
- [x] 错误捕获
- [x] 基础设置
- [x] 智能设置
- [x] 关于窗口
- [x] 待机帧切换
- [x] 进入时选择资源包
- [x] 双击跳跃
- [x] 范围限制的随机行走
- [x] 配置文件热保存

#### 3.养成系统
- [x] 养成架构、窗口
- [x] debug
- [x] 物品接口
- [x] 营养资源
- [x] 属性值
- [x] 状态接口
- [x] 事件管理器
- [ ] 状态条展示tick变化值
- [ ] 觅食
- [ ] 生病
- [ ] 存档系统
- [x] 模组接口
- [x] 模组支持注册i18key
- [x] 模组覆盖i18汉化
- [ ] 模组管理器: 调整模组注册顺序

### 资源

```
# 路径 ./resources/PetArt/{自定义}
分辨率 128 x 128
待机动画    .png    1+1 帧  其中 default.png 为主要帧
走路动画    .png    4 帧    第 2、3 帧向左移动 2 像素（无需反转资源）
跳起动画    .png    1 帧
拖动动画    .png    1 帧
渐入动画    .gif    1 组    帧数任意（无需反转资源，建议头尾增加缓冲帧）

# 路径 ./
分辨率 128 x 128
桌角图标    .png    1 张    用于显示小图标，必须添加
桌面图标    .ico    1 张    仅用于打包，不会被编码
```  

通过base64编码打包的资源，运行资源编码器pack_resources.py即可
```
resources/{name}.json
```

源文件存储地址
```
# 待机动画
default.png     # 主要帧
default2.png    # 待机动画使用

# 走路动画
walk.png
walk2.png
walk3.png
walk4.png       # 拷贝default.png即可

# 双击跳起
jump.png

# 拖动动画
pickup.png

# 空白代替帧
None.png

# 桌角图标
logo.png
```

### 开发块
##### 框架
- 设计：LyceenAiro
- 代码：LyceenAiro + Copilot
##### 桌宠动画及脚本
- 设计：LyceenAiro
- 代码：LyceenAiro + Copilot
##### 设置
- 设计：LyceenAiro + Copilot
- 代码：Copilot 
##### i18
- 设计：LyceenAiro + Copilot
- 代码：Copilot
- 重构：Copilot
##### 资源选择器
- 设计：Copilot
- 代码：Copilot 
##### 资源编码器
- 设计：LyceenAiro + Copilot
- 代码：Copilot

#### 美术资源(拒绝生成式AI创建美术资源)
- 动画资源支持：犬牙冢
- 动画资源细化、创建：LyceenAiro

## LICENSE
[BSD 3-Clause License](./LICENSE)