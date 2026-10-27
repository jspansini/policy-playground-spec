---
inclusion: auto
name: fluxo-git
description: Convenções de branch, commit e pull request do time CredIA Girls. Use ao criar branch, escrever mensagem de commit, abrir ou revisar PR.
---

# Fluxo de trabalho no Git

- **Nunca commite direto no `main`.** Toda mudança entra por PR revisado por outra integrante.
- **Branch por assunto:** `tipo/descricao-curta`, por exemplo `feat/hooks-validador` ou `docs/steering`. Se houver issue, o número pode entrar no nome.
- **Commits** no padrão Conventional Commits, em português: `feat(validador): bloqueia ciclo no DAG`. Tipos: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`.
- **PR** pelo template de `.github/pull_request_template.md`, citando a issue, se houver (`Closes #7`), e os requisitos tocados (R1–R16, NFRs, ADRs).
- **Review:** o `CODEOWNERS` pede revisão de todo o time. Comente com sugestão concreta; aprove só depois de rodar os testes.
- Antes de abrir o PR, rode `python3 -m unittest discover -s tests -v`.

Detalhes em #[[file:docs/colaboracao/fluxo-de-trabalho.md]].
