# 资源雷达 · GitHub Pages 云端版

**特别感谢原作者 [ZiChuanLan](https://github.com/ZiChuanLan) 开源的 [Freebie Radar](https://github.com/ZiChuanLan/freebie-radar)。** 本项目是基于原项目采集能力的独立静态适配版，保留 MIT 许可及原始版权声明，不代表原作者官方服务。本项目复用固定提交 9191745d6368ca34b89f436abe2df66b9dd17d6e 的采集器，新增云端增量审核、静态网页与每日精选。欢迎支持原项目。

## 功能
- GitHub 托管 runner 每两小时采集，计划每日 12 次；北京时间 20:30 生成最多 12 条精选。
- AI/开发者 4 条、电商 3 条、影音会员 3 条、其他 2 条；不足不凑数。
- 10 个公开数据源：LINUX DO、V2EX 两个节点、什么值得买、福利吧、IT之家、NodeSeek、OpenRouter、Epic、GamerPower。
- 淘宝、京东、拼多多、视频及音乐会员优惠通过公开聚合源发现，不是直接调用平台官方商品接口。
- 不推送，不开放本机端口，不使用 Lighthouse，不需要常驻服务器。
- 只读公开网页：分类、搜索、日期、近期资源和采集状态；无在线管理后台。

## 部署
1. Settings → Secrets and variables → Actions → New repository secret：名称 MIMO_API_KEY，值为自己的 MiMo API Key。不要提交密钥、数据库、Cookie、日志。可选 Actions Variable MIMO_MODEL，默认 mimo-v2.6-flash。
2. Settings → Pages → Build and deployment → Source: GitHub Actions。
3. Actions → Radar cloud collection and Pages → Run workflow（main）。可勾选 daily 提前生成当日精选；不勾选则正常采集。
4. 等待 collect / publish / deploy 全部成功，从部署日志或 Settings → Pages 获取真实网址。

## 运行边界
采集与审核分离，每源最多 15 条候选；每轮最多 24 条新候选送审，每批 2 条、串行，3 次批次错误即停止。已成功审核的指纹保留 14 天，不重复送审。无有效审核结果时保留上次快照。待审原始正文不持久化，仅在下次仍被源返回时重试。近 3 天资源、14 天日报历史；近期日报按链接和规范化标题去重。云端源可达性和模型实际响应需首次运行验证。模型 API 按实际用量收费。定时任务不保证精确准时，公开仓库长期无活动可能被停用。

## 安全
原始候选及 SQLite 仅存临时 runner；公开快照仅包含裁剪后的标题、来源、受限 HTTPS 链接、日期、质量及受控理由。网页以 textContent 渲染，不注入外部 HTML，禁用外部脚本。定时工作流不处理 Pull Request，采集 job 仅读，发布 job 才可提交公开 JSON，部署 job 才可使用 Pages 权限。MiMo Key 仅传给审核步骤。公开仓库及网页可被其他人访问，历史提交也可能留存公开记录。AI 评分不是官方核验，请核对原平台价格、资格、截止时间与续费条件。遵守来源条款和合理抓取频率。

## 测试
```sh
python3 -m unittest discover -s tests -v
node --check scripts/collect.mjs
node --check site/app.js
```
上述测试为无网络检查，云端首次运行才是端到端验收。
