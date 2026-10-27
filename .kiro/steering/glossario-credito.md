---
inclusion: fileMatch
fileMatchPattern: [".kiro/specs/**", "tools/policy_spec/**", "tests/**"]
---

# Glossário de crédito

Use estes termos exatamente assim em código, testes e documentos.

| Termo                         | Significado                                                                                                                                           |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Plataforma de política de crédito | Ambiente interno de políticas de crédito: definições, estudos e conhecimento de domínio                                                               |
| Policy Spec                   | JSON consolidado que representa a política: `policy`, `stages`, `rules`, `variables`, `parameters`, `dag`, `motivos`, `validation_map`, `output_vars` |
| Áreas da política             | Extraction, ETL, Hard filters, Final base. O mapeamento estágio → área fica no arquivo de extensions (OQ-18)                                          |
| Motivo de Decisão             | Base histórica de decisões de crédito em produção; referência de comparação do impacto. Tabela DynamoDB existente, somente leitura                    |
| Estudo                        | Computação determinística da plataforma de política de crédito que produz impacto; fonte da verdade do número                                                       |
| Policy DAG                    | Grafo de dependências entre regras; a execução respeita `dag.execution_order`                                                                         |
| Hipótese                      | Mudança proposta e testável; é proposta, não evidência                                                                                                |
| Cenário                       | Baseline imutável + overrides de parâmetros, confirmado por uma pessoa                                                                                |
| Finding                       | Observação ou sugestão; tem `investigationState` e `evidenceLevel` independentes                                                                      |
| Renda mínima (P001)           | Parâmetro do fixture usado pela regra R005; baseline R$ 2.500                                                                                         |
| Comprometimento máximo (P002) | Parâmetro do fixture usado pela regra R006; baseline 35%                                                                                              |
| Faixa (R007)                  | ALTA a partir de R$ 5.000, MEDIA a partir de R$ 3.000, senão BASICA. Os cortes são literais, somente leitura no MVP                                   |

O fixture é **100% sintético**: não representa política, dado ou resultado real de nenhuma instituição.

#[[file:.kiro/specs/policy-playground/fixtures/policy-playground-demo-policy-README.md]]
