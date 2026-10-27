---
inclusion: always
---

# Produto: Policy Playground

O Policy Playground é o ambiente em que o especialista de políticas de crédito PF testa hipóteses sem escrever SQL ou Python. Ele vê o impacto calculado por execução determinística e investiga, com apoio de IA, cenários que ninguém tinha pensado em perguntar.

## Para quem

- **Especialista de políticas** (usuário principal): formula e testa hipóteses, decide se a mudança avança.
- **Aprovador de risco**: revisa a evidência e registra Accept, Reject ou Defer.
- **Analista de dados**: reproduz execuções a partir das versões registradas.
- **Engenharia do motor de decisão**: recebe a mudança como PR para revisão.

## Princípio que não se negocia

**AI proposes. Deterministic execution proves. Humans decide.** Detalhes em #[[file:.kiro/steering/principios-ia-e-evidencia.md]].

## Escopo do MVP

- Consome e valida um Policy Spec já consolidado (não o produz).
- Roda sobre o fixture 100% sintético; todo número é rotulado SIMULADO.
- Código, testes e PR real para a plataforma de política de crédito são condicionais (OQ-9).

## Métricas que importam

Lead time de hipótese até evidência (meta: de 3 dias para 1), handoffs por hipótese (de 3 para 1) e share de findings da IA marcados como relevantes (meta: 55%).

## Fontes

- #[[file:docs/working-backwards.md]]
- #[[file:.kiro/specs/policy-playground/requirements.md]]
