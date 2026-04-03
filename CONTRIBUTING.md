\# Welcome to Observal 🎉



Thank you for considering contributing to \*\*Observal\*\*. Contributions of all kinds are welcome—bug fixes, new features, or documentation improvements.



This guide outlines the workflow to help you contribute effectively.



\---



\## 🛠️ 1. Fork and Clone the Repository



1\. \*\*Fork\*\* the repository using the GitHub "Fork" button.

2\. \*\*Clone\*\* your fork locally:



```bash

git clone https://github.com/YOUR-USERNAME/Observal.git

cd Observal

```



3\. Add the upstream repository:



```bash

git remote add upstream https://github.com/BlazeUp-AI/Observal.git

```



\---



\## 📦 2. Development Environment Setup



Ensure the following tools are installed:



\* \*\*Docker \& Docker Compose\*\* – for PostgreSQL, ClickHouse, Redis

\* \*\*uv\*\* – Python dependency management (Python 3.11+)

\* \*\*Node.js (20+)\*\* – frontend (Vite, React)

\* \*\*Git\*\*



\---



\## 🚀 3. Run the Project Locally



1\. Create your environment file:



```bash

cp .env.example .env

```



2\. Start backend services:



```bash

cd docker

docker compose up --build -d

cd ..

```



3\. Install CLI and start the app:



```bash

uv tool install --editable .

observal init

```



Services will start at:



\* API → http://localhost:8000

\* Web UI → http://localhost:3000



\---



\## 💅 4. Code Style \& Linters



We enforce code quality using:



\* \*\*Python\*\* → `ruff`

\* \*\*TypeScript/React\*\* → `ESLint`

\* \*\*Docker\*\* → `hadolint`



Commands:



```bash

make format   # Auto-format code

make lint     # Run linters

```



\### Pre-commit Hooks



```bash

make hooks

```



\---



\## 🧪 5. Running Tests



Run all tests:



```bash

make test

```



Verbose mode:



```bash

make test-v

```



All tests must pass before submitting a PR.



\---



\## 🌿 6. Branch Naming Convention



Do not commit directly to `main`.



Use prefixes:



\* `feature/` → new features

\* `fix/` → bug fixes

\* `docs/` → documentation



Examples:



```

feature/agent-eval

fix/docker-compose-typo

docs/update-readme

```



\---



\## 💬 7. Commit Message Convention



Follow \*\*Conventional Commits\*\*:



```

<type>(<scope>): <description>

```



Examples:



```

feat(cli): add telemetry ingestion command

fix(ui): resolve overflow issue on trace explorer

docs: add contributing guide

```



\---



\## 🤝 8. Pull Request Process



1\. Push your branch to your fork

2\. Open a PR against `main`

3\. Ensure:



&#x20;  \* All tests pass

&#x20;  \* Linters pass



\### Review Process



\* Maintainers will review your PR

\* Be responsive to feedback

\* Update your code if requested



\---



\## 🐛 9. Issues



Before coding, check existing issues.



\* \*\*Bug reports\*\* → include reproduction steps and environment details

\* \*\*Feature requests\*\* → describe the idea clearly



Discuss major features before implementing them.



\---



\## ❓ 10. Support



If you need help:



\* Use \*\*GitHub Discussions\*\*

\* Comment on issues

\* Join future community channels (Discord/Slack)



\---



Happy coding 🚀



