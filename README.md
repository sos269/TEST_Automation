# Web UI 自动化项目

基于 **Python + Playwright** 的轻量级 Web 端 UI 自动化工具，包含两个阶段：

1. **生成**：扫描测试站点中的页面与输入控件，生成可审阅的 YAML 用例。
2. **执行**：按 YAML 用例在 Chromium 中执行，并以非零退出码报告失败。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
playwright install chromium
```

## 使用

1. 复制并修改 `config/target.example.yaml`，指定**测试环境**的 `start_url`、允许扫描的 `allowed_hosts` 与填写样例数据。
2. 生成初始用例：

```powershell
ui-autotest generate --config config/target.yaml --cases tests/generated_cases.yaml
```

3. 审核 `tests/generated_cases.yaml`，删除不应执行的用例，并为关键业务流程补充断言。
4. 执行用例：

```powershell
ui-autotest execute --config config/target.yaml --cases tests/generated_cases.yaml
```

## AI 自动生成

配置模型 API 后，可用 AI 基于已扫描页面的标题、控件标签、选项和稳定选择器规划测试用例：

```powershell
$env:OPENAI_API_KEY = "<your-api-key>"
ui-autotest generate --ai --config config/target.yaml --cases tests/ai_cases.yaml
ui-autotest execute --config config/target.yaml --cases tests/ai_cases.yaml
```

AI 不会接收页面正文、Cookie、输入内容或登录凭据，只接收最小化控件元数据。生成结果仍会在本地校验：URL 必须已被扫描、选择器必须来自页面快照、下拉值必须真实存在，高风险按钮不可点击。`ai.allow_submit` 默认为 `false`；开启后也只能点击页面快照中允许的提交控件。请始终在测试环境运行并人工审核生成的 YAML。

### 多模型 API 配置

`ai.provider` 支持以下值：

- `openai_compatible` / `openai`：OpenAI、DeepSeek、通义、智谱、vLLM、Ollama 等 Chat Completions 接口；通过 `base_url` 切换服务。
- `anthropic` / `claude`：Anthropic Messages API。
- `gemini` / `google`：Google Gemini API。

示例：

```yaml
ai:
  provider: "ollama"
  model: "qwen2.5:7b"
  base_url: "http://localhost:11434/v1"
  api_key_env: "OLLAMA_API_KEY"
```

Anthropic 使用 `base_url: "https://api.anthropic.com/v1"` 和 `ANTHROPIC_API_KEY`；Gemini 使用 `base_url: "https://generativelanguage.googleapis.com/v1beta"` 和 `GEMINI_API_KEY`。API Key 只从 `api_key_env` 指定的环境变量读取，不写入 YAML。

## YAML 用例格式

```yaml
cases:
  - name: 登录邮箱可编辑
    tags: [smoke]
    steps:
      - action: navigate
        value: https://test.example.com/login
      - action: fill
        selector: '[data-testid="email"]'
        value: tester@example.com
      - action: expect_value
        selector: '[data-testid="email"]'
        value: tester@example.com
```

支持的动作：`navigate`、`expect_title`、`fill`、`expect_value`、`expect_visible`、`select_first`、`select_option`、`click`。其中 AI 仅可点击快照中明确标记为安全的元素。

## 设计边界

- 生成器只访问 `allowed_hosts` 内的 HTTP(S) 页面，并限制扫描页面和控件数量。
- 默认生成访问、输入和下拉控件可用性检查；不会自动点击按钮或提交表单，避免产生副作用。
- 推荐在页面中提供稳定的 `data-testid`，生成器会优先使用它作为选择器。
- 登录凭据和真实业务数据请从 CI 密钥或环境变量注入，禁止写入配置文件与仓库。
