# 人工维护区（你改这里，提交后自动重新部署）
- `programs.yaml`：长期项目 / 无法自动抓取的活动来源
- `foodbanks.yaml`：食物银行目录
每条必须有 `last_verified`（YYYY-MM-DD）和 `sources`（一手 URL）。不知道的字段写 null，不要猜。

programs 字段：id, org, title, title_zh, category(tree-planting|environment|food-bank|other), url, signup_url, min_age(int|null), credit(stated|not-stated), schedule, schedule_zh, area, notes, notes_zh, last_verified, sources[]
foodbanks 字段：id, name, area, address, url, find_food_url, volunteer_url, volunteer_min_age(int|null), notes, notes_zh, last_verified, sources[]
