# Windows 重装 PostgreSQL（独立安装，不用 checkmystat）

适用于：本机 `C:\Program Files\PostgreSQL\17` 安装不完整、5432 连不上、想单独给榴莲 Agent 用库。

---

## 一、卸载旧安装

### 1. 停止可能残留的服务

PowerShell **以管理员身份**运行：

```powershell
Get-Service *postgres* -ErrorAction SilentlyContinue | Stop-Service -Force
sc.exe delete postgresql-x64-17
```

（若提示服务不存在，忽略即可。）

### 2. 卸载程序

任选一种：

**方式 A：设置里卸载**

1. `Win + I` → **应用** → **已安装的应用**
2. 搜索 `PostgreSQL`
3. 有则点 **卸载**，按向导走完

**方式 B：直接删目录（你当前很可能是残缺安装）**

管理员 PowerShell：

```powershell
Remove-Item "C:\Program Files\PostgreSQL" -Recurse -Force -ErrorAction SilentlyContinue
```

### 3. 清理环境变量（可选）

1. `Win + R` → `sysdm.cpl` → **高级** → **环境变量**
2. 在 **Path** 里删掉含 `PostgreSQL\17\bin` 的条目

---

## 二、全新安装（推荐 winget）

管理员 PowerShell：

```powershell
winget install PostgreSQL.PostgreSQL.17 --accept-package-agreements --accept-source-agreements
```

安装过程中会提示设置 **超级用户 `postgres` 的密码**，请牢记（下面用 `你的密码` 代替）。

> 也可装 18：`winget install PostgreSQL.PostgreSQL.18 ...`

### 或：官网安装包

1. 打开 https://www.postgresql.org/download/windows/
2. 下载 **PostgreSQL 17** Windows x86-64 安装包
3. 运行安装向导，建议选项：
   - 端口：`5432`（默认）
   - 超级用户密码：自设并记住
   - Locale：默认即可
   - 组件：PostgreSQL Server、pgAdmin 4、Command Line Tools **都勾选**
4. 结束时勾选 **Launch Stack Builder** 可跳过

---

## 三、确认安装成功

PowerShell（普通权限即可）：

```powershell
Get-Service *postgres*
```

应看到类似 `postgresql-x64-17`，状态 **Running**。

```powershell
& "C:\Program Files\PostgreSQL\17\bin\pg_isready.exe" -h localhost -p 5432
```

应输出：`accepting connections`

---

## 四、给榴莲 Agent 建库

### 1. 修改 `d:\agent\.env`

```env
DATABASE_URL=postgresql://postgres:你的密码@localhost:5432/durian_agent
```

### 2. 初始化

```bash
cd d:\agent
pip install psycopg[binary]
python scripts/init_postgres.py --create-db
```

成功会看到：`表结构初始化完成（postgresql）`

### 3. 验证

```bash
uvicorn src.main:app --reload --host 127.0.0.1 --port 8080
```

浏览器打开：http://localhost:8080/api/v1/health  

应含：`"database": "postgresql"`

---

## 五、常用命令

| 操作 | 命令 |
|------|------|
| 启动服务 | `Start-Service postgresql-x64-17` |
| 停止服务 | `Stop-Service postgresql-x64-17` |
| 进命令行 | `"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres` |
| 图形管理 | 开始菜单搜 **pgAdmin 4** |

---

## 六、常见问题

**安装后仍连不上 5432**

- 确认服务在运行：`Get-Service postgresql-x64-17`
- 防火墙一般本地回环不需改；公司电脑可问 IT

**密码忘了**

- 用 pgAdmin 重置，或参考官方文档修改 `pg_hba.conf` 临时 trust 后改密

**和 checkmystat 冲突吗**

- 不冲突。checkmystat 用 **5433**，独立安装用 **5432**，互不影响
