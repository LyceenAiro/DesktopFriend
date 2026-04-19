## 这是一个桌宠

### 目前开发进度

#### 1. 框架搭建

- [X] 注册表框架
- [X] 基础的画面显示框架
- [X] 拖动行为
- [X] 右键功能列表
- [X] 在最顶层功能
- [X] 小图标功能列表
- [X] 最小化图标隐藏
- [X] 桌宠行走功能
- [X] 补全动作图像
- [X] github库发布

#### 2. 更多基础功能

- [X] 进入推出渐入动画
- [X] 资源文件编码
- [X] 项目打包
- [X] 资源包格式加载
- [X] 错误捕获
- [X] 基础设置
- [X] 智能设置
- [X] 关于窗口
- [X] 待机帧切换
- [X] 进入时选择资源包
- [X] 双击跳跃
- [X] 范围限制的随机行走
- [X] 配置文件热保存

#### 3.养成系统

- [X] 养成架构、窗口
- [X] debug
- [X] 物品接口
- [X] 营养资源
- [X] 属性值
- [X] 状态接口
- [X] 事件管理器
- [X] 状态条展示tick变化值
- [X] 上限修正兼容
- [X] 状态兼容使用百分比赋予buff
- [X] 事件系统支持检测所需物品启动
- [X] buff支持变更属性
- [X] 重构属性UI
- [X] 支持使用json注册属性值
- [X] 休眠模式（挂后台或太久没移动鼠标影响tick速率）
- [X] 物品唯一持有属性
- [X] 持有的物品支持永久变更属性值
- [X] 养成系统搜索功能
- [X] 事件触发被属性值影响
- [X] 等级系统玩法(扩展养成玩法)
- [X] 死亡逻辑
- [X] 玩法闭环
- [X] 存档系统（导出、导入功能，存档栏）
- [X] 模组覆盖注册逻辑
- [ ] 模组管理器: 调整模组注册顺序
- [ ] 重构动作触发模组（疲惫，休息，死亡）
- [ ] 状态反馈图标（饥饿、渴、生病等）
- [X] 挂机随机buff产生
- [ ] 图鉴系统，以及收集进度（如果是debug还支持直接查看全图鉴）
- [X] 模组接口（未来开发0.3内完再次整备）
- [X] 模组支持注册i18key
- [X] 模组覆盖i18汉化
- [X] log系统优化（将某些日志归类为debug，且在开发者模式中支持调整log等级）
- [ ] 日志记录补全

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
- 测试：LyceenAiro

##### 设置及其扩展

- 设计：LyceenAiro + Copilot
- 代码：Copilot
- 测试：LyceenAiro

##### i18

- 设计：LyceenAiro + Copilot
- 代码：Copilot
- 重构：Copilot
- 测试：LyceenAiro

##### 资源选择器

- 设计：Copilot
- 代码：Copilot
- 测试：LyceenAiro

##### 资源编码器

- 设计：LyceenAiro + Copilot
- 代码：Copilot
- 测试：LyceenAiro

##### life模块

- 设计：LyceenAiro
- 代码：LyceenAiro + Copilot
- 测试：LyceenAiro

#### 美术资源(拒绝生成式AI创建美术资源)

- 动画资源支持：犬牙冢
- 动画资源细化、创建：LyceenAiro

## LICENSE

[BSD 3-Clause License](./LICENSE)
