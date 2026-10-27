# Policy Playground — insumo sintético para Kiro Design

## Propósito

Fixture **100% fictício**, criado para a fase de **Design** do Kiro Spec-Driven Development. Não representa a política real de Microcrédito, nem dados, código, regras, valores, parâmetros ou resultados do Politica/FICO. **Não usar para decisões de crédito.**

## Base conceitual

O relatório fotografado da plataforma de política de crédito descreve um JSON com nove seções: `policy`, `stages`, `rules`, `variables`, `parameters`, `dag`, `motivos`, `validation_map`, `output_vars`. O artefato analisado no relatório tinha 109 regras, quatro etapas e dependências. Este fixture reduz a escala para **9 regras**, **4 etapas**, **10 variáveis**, **2 parâmetros** e **3 motivos**, preservando o formato conceitual, e, desde a revisão 1.2, é acompanhado de um arquivo de extensões e de um conjunto sintético de **12 propostas**, ambos separados do Policy Spec. Os valores e a lógica das regras foram inventados para demonstração.

## Fluxo demonstrativo

1. Extrair renda, idade e comprometimento de um payload sintético.
2. Aplicar filtros de elegibilidade por idade, renda mínima e comprometimento.
3. Classificar faixa e consultar uma matriz fictícia de oferta.
4. Consolidar um resultado simulado e rastrear os motivos.

## Cenário-chave para a interface

O especialista seleciona a política, abre a regra **R005**, altera `renda_minima` de **2500** para **3000**, compara baseline e cenário, vê as dependências e pede uma investigação complementar. O agente pode propor hipóteses, mas **não inventa evidências**. Os estudos determinísticos reais não estão conectados a este fixture: qualquer resultado demonstrado precisa ser identificado como **simulado**.

## Decisões de design a explorar

- Visualização de regras atômicas, parâmetros e DAG.
- Editor de thresholds com preview, validação e diff baseline/cenário.
- Interpretação de `json_extract`, `case_when` e `matrix_lookup`.
- Trilhas de auditoria: regra, variável, parâmetro, origem e motivo.
- Findings de IA separados entre _hipótese sem comprovação_ e _finding com evidência_.
- Estados de UI para erro de schema, dependência ausente, execução indisponível e ausência de evidência.

## Gaps observados no relatório

- `consumed_by` não vem preenchido: derivar invertendo os `inputs` das regras.
- Parâmetros extraídos automaticamente podem duplicar os parâmetros conhecidos: deduplicar.
- Ordem de execução e fluxos paralelos precisam ser representados explicitamente.

## Arquivos do fixture

| Arquivo                                  | O que é                                                                                        | Quem produz                          |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------ |
| `policy-playground-demo-policy.json`     | O Policy Spec sintético: as nove seções originais, **sem nenhuma alteração**                   | Etapa anterior ao Playground (R16.3) |
| `policy-playground-demo-extensions.json` | Metadados próprios do Playground que **complementam** o Policy Spec, referenciando-o pelos ids | Playground (revisão 1.2)             |
| `policy-playground-demo-dataset.json`    | 12 propostas sintéticas versionadas para o `SimulatedRunner`                                   | Playground (revisão 1.2)             |

O Policy Spec é consumido e validado pelo Playground, mas nunca modificado. Por isso, tudo o que a revisão 1.2 acrescenta fica nos dois arquivos complementares.

## O que o arquivo de extensões acrescenta

| Seção                                                                          | Para que serve                                                                                                                            | Origem                            |
| ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `extends` (`file`, `policy_id`, `source_commit`)                               | Amarra as extensões a uma versão específica do Policy Spec; se não bater, as extensões são rejeitadas e o Policy Spec continua carregando | R16.2                             |
| `policy_source` (`vcs`, `repository`, `path`, `commit`)                        | Explicita que a versão da política é um commit Git; `commit` deve ser igual a `source_commit` do Policy Spec                              | Decisão do time D-Q2; R14.6       |
| `stage_area`                                               | Mapeia cada etapa para uma das quatro áreas da política                                                                           | R1.2; OQ-18                       |
| `parameter_domains` (`editable`, `type`, `min`, `max`, `step`)                 | Limites que o editor visual aplica; um valor fora do domínio é rejeitado com o intervalo aceito                                           | R2.4, R4; Notion FR-03            |
| `datasets` (`dataset_version`, `kind`, `contains_pii`, `file`, `record_count`) | Aponta para o conjunto sintético; a `dataset_version` entra na chave de idempotência e permite reproduzir cada execução                   | Decisão do time D-Q6; design §9.4 |

### Mapeamento das etapas para as quatro áreas da política (provisório)

Os requisitos (R1.2) pedem que cada elemento indique a área da política de origem: Extraction, ETL, Hard filters ou Final base. As etapas deste fixture têm outros nomes, então o mapeamento fica em `stage_area` no arquivo de extensões:

| Etapa do fixture | Área da política       | Observação                                            |
| ---------------- | ------------------------ | ----------------------------------------------------- |
| 01 Extração      | Extraction               | Leitura e `cast` do payload sintético.                |
| 02 Elegibilidade | Hard filters             | Regras `filter` (R004–R006) ligadas a motivos.        |
| 03 Oferta        | Final base               | Derivação de faixa e limite que compõem a base final. |
| 04 Consolidação  | Final base               | Resultado consolidado.                                |

O fixture **não tem etapa própria de ETL**: as transformações estão embutidas na extração (`cast`). Esse mapeamento é uma escolha de demonstração e não descreve como a política real se distribui entre as áreas (OQ-18).

### Cobertura do dataset sintético

Os 12 registros foram escolhidos à mão para exercitar todos os ramos das regras. O resultado esperado não está gravado no arquivo: os testes devem derivá-lo das regras do fixture (tasks.md, task 7).

| Registro | Renda | Idade | Compr. % | Perfil | O que exercita                                             |
| -------- | ----- | ----- | -------- | ------ | ---------------------------------------------------------- |
| S01      | 2.200 | 30    | 20       | A      | Renda abaixo do corte atual (R005)                         |
| S02      | 2.500 | 41    | 25       | B      | Renda exatamente no corte atual (`>=`)                     |
| S03      | 2.700 | 35    | 30       | A      | Faixa BASICA aprovada com corte 2.500; reprovada com 3.000 |
| S04      | 2.950 | 52    | 18       | B      | Idem, perfil B                                             |
| S05      | 3.000 | 28    | 22       | A      | Renda exatamente no novo corte; faixa MEDIA                |
| S06      | 4.200 | 45    | 34       | B      | Faixa MEDIA, comprometimento perto do limite               |
| S07      | 4.800 | 33    | 36       | A      | Reprovado por comprometimento (36 > 35, R006)              |
| S08      | 5.000 | 39    | 15       | A      | Renda no limite da faixa ALTA (R007)                       |
| S09      | 7.500 | 60    | 28       | B      | Faixa ALTA                                                 |
| S10      | 6.100 | 17    | 10       | A      | Reprovado por idade (R004)                                 |
| S11      | 2.800 | 19    | 40       | B      | BASICA reprovada por comprometimento nos dois cenários     |
| S12      | 3.100 | 18    | 35       | B      | Idade e comprometimento exatamente nos limites             |

**Uso no cenário-chave.** Com `renda_minima` em 2.500, os registros S02, S03 e S04 são aprovados na faixa BASICA. Com 3.000, nenhum registro aprovado cai na faixa BASICA. É o finding estrutural que o gerador G2 aponta (design §10.3), e o dataset permite mostrá-lo com uma execução `SIMULADO`, sem inventar números.

## Limites do fixture

Este arquivo **não é uma implementação executável**. Expressões são strings para apoiar o desenho do contrato; ainda será preciso decidir parser/avaliador e semântica de nulos, casting e erros. `perfil` é uma entrada externa sintética para demonstrar `matrix_lookup`. A estrutura de notebooks e DAG é simplificada.

## Princípio do produto

**AI proposes. Studies prove. Humans decide.**

## Sugestão de uso no Kiro

Adicione os quatro arquivos (`policy-playground-demo-policy.json`, `policy-playground-demo-extensions.json`, `policy-playground-demo-dataset.json` e este README) ao repositório local como material de referência. Na fase de design, peça ao Kiro para usar o JSON como fixture, mantendo `requirements.md` como fonte dos requisitos e documentando decisões, contratos, componentes, fluxos e trade-offs em `design.md`. Não apresente a política sintética como extração real da plataforma de política de crédito.
