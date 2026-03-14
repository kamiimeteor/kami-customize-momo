# momo Persona Files

这个目录存放 `momo` 的身份层配置。

- `CONFIG.json`
  - 结构化运行时配置
  - 例如名字、关系定位、语气、主动性策略、语音播报开关
- `IDENTITY.md`
  - 角色身份
- `SOUL.md`
  - 性格和气质
- `USER.md`
  - 用户画像
- `RULES.md`
  - 行为边界
- `HEARTBEAT.md`
  - 未来主动思考的低频规则

这些文件一起构成项目的稳定人格配置来源。

- `CONFIG.json`
  - 适合程序读取和运行时展示
- `*.md`
  - 适合写清楚设定本身和长期约束

后续如果接入记忆、主动提问、语音回复，都应该优先读取这里，而不是把 persona 写死在代码里。
