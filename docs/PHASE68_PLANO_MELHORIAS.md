# Plano detalhado de melhorias — atualizado depois da Fase 69

Data: 2026-09-05. Base de implementação proposta: **`8b675a9`**, não a versão anterior à resposta de Claude. Estado: **plano, sem execução de correções**. Os checkboxes seguintes ficam por fazer até haver implementação, testes e evidência. Não confundir a conclusão da auditoria com a conclusão destas melhorias.

Este plano consolida a Fase 64 já existente e reabre apenas as garantias da Fase 69 que os testes novos mostraram incompletas. Não propõe outra arquitetura paralela, outro supervisor ou integração com PA3.

## Resultado pretendido

O sistema deve conseguir dizer, com provas: “guardei precisamente esta afirmação, dessa pessoa e nessa data; recordei a versão adequada; executei só o que foi autorizado; verifiquei este resultado; e, quando pediste para retirar/cancelar, isso deixou de influenciar as próximas ações”.

Uma boa resposta ocasional não basta; uma base canónica correta sem uso nas respostas também não basta. Cada camada tem um contrato e uma avaliação independente.

## O que NÃO é preciso refazer

Na Fase 69 confirmaram-se: resolução do alias antes do bloqueio de ferramentas conhecidas; bloqueio do materializador HTML no caso testado sem autorização; distinção lexical número/unidade; memória em português nos exemplos antigos; separação cão/gato; cancelamento curto de plano ativo; proteção contra `done` sem nenhuma ferramenta anterior; tombstones de regras; remoção do plano ao apagar sessão; raw content em `memory_search` e recall de etapas; fallback canónico em pesquisa vazia; eventos/UI e restauro de ferramentas bloqueadas; correções dos avaliadores para pesquisa falhada e algumas negações.

Conservar estes controlos. As novas tarefas aprofundam os contratos, não apagam o progresso. A suite atual tem **452 testes aprovados**, independentemente reexecutados nesta auditoria.

## Ordem de execução e dependências

| Lote | Prioridade | Resultado | Depende de | Gate de saída |
|---|---|---|---|---|
| M0 | Imediata | Evidência imutável e ambiente de ensaio protegido | — | Cada resultado identifica código, modelos, dados e configuração; nenhum replay escreve em produção. |
| M1 | P0 para ações | Autoridade por ação, argumentos e âmbito; revogação persistente | M0 | Todos os casos conhecidos de execução não autorizada bloqueados antes do efeito. |
| M2 | P0 para autonomia | Recibos por etapa e conclusão verificável | M1 | Nenhum `done` sem pós-condição; falha parcial nunca é sucesso total. |
| M3 | P0 para memória | Afirmações com entidade, contexto e evidência | M0 | Casos conhecidos sem corrupção; precisão/cobertura medidas separadamente. |
| M4 | P1 | Um contrato de leitura/escrita/retração em todos os caminhos | M3 | Paridade de APIs, CLI, ferramentas, planos e UI. |
| M5 | P1 | Respostas ligadas a factos/recibos e verificação final | M2 + M4 | Confirmações correspondem ao alvo, valor e ação reais. |
| M6 | P1, começa em M0 | Benchmark independente e comparação Fu | M0; promoção após M3–M5 | Ganho repetido em casos reservados, com orçamento/custo controlados. |
| M7 | P1/P2 | Ciclo de vida, concorrência, configuração e UI completos | M1–M5 | Restart/crash/cancel/falha/restauro verificados de ponta a ponta. |

P0 nesta tabela significa bloquear a próxima promoção dessas capacidades, não chamar todos os achados “críticos” de segurança. Memória e ações podem ser implementadas em lotes separados; a decisão de delegar trabalho fica com o utilizador.

## M0 — Congelar a experiência antes de mexer

Módulos a reutilizar: utilitários de benchmark existentes, `config`, `settings`, fixtures de testes e scripts da auditoria.

- [ ] M0.1 Criar uma execução identificada por commit + timestamp/ID, com diretório novo; nunca sobrescrever resultados de outra versão. Registar SHA256 do corpus e das configurações, digest dos modelos Ollama, versão do runtime, hardware e warm/cold start.
- [ ] M0.2 Separar fixtures públicas/sintéticas de dados pessoais. O executor recebe obrigatoriamente `db_path` e workspace temporários; rejeita o caminho real antes de construir `AgentEngine`.
- [ ] M0.3 Proibir que `--dry` instancie um motor mutável ou execute migrações. Usar SQLite read-only para diagnóstico/importação simulada.
- [ ] M0.4 Congelar os 56 contratos antigos, com migração explícita de duas expectativas `pet.name` para os novos campos de espécie, preservando o requisito original. Acrescentar os 35 desafios novos como regressões, sem os apresentar como conjunto reservado.
- [ ] M0.5 Preparar novos conjuntos de desenvolvimento e avaliação reservada por família semântica, não apenas substituindo nomes nas frases já usadas. Quem implementa não ajusta padrões às respostas do conjunto final.

Gate: falha intencional num caso obriga o relatório a ficar vermelho; uma ferramenta falhada não conta como sucesso; erro ambiental recebe categoria própria; métricas não desaparecem quando há timeout. Reexecutar a mesma fixture determinística produz o mesmo estado esperado.

Evidência de necessidade: a Fase 69 incorporou os artefactos e voltou a executar scripts que escrevem em caminhos fixos da Fase 68. Os resultados históricos precisam de identificação imutável para não parecerem atuais. O próprio relatório de Claude documenta um teste de cidade na base real e uma reversão; esta auditoria não repetiu essa operação nem verificou uma restauração completa.

## M1 — Fechar a autoridade, aproveitando `authority.py`

Ficheiros donos: [authority.py](C:/Users/nora/hmg-fu/hmgfu/authority.py), [turn_events.py](C:/Users/nora/hmg-fu/hmgfu/turn_events.py), [tool_loop.py](C:/Users/nora/hmg-fu/hmgfu/tool_loop.py), [toolsys.py](C:/Users/nora/hmg-fu/hmgfu/toolsys.py), [session_plans.py](C:/Users/nora/hmg-fu/hmgfu/session_plans.py), [widgets.py](C:/Users/nora/hmg-fu/hmgfu/widgets.py).

- [ ] M1.1 Substituir o booleano de permissão global por uma decisão sobre ferramenta canónica + tipo de efeito + alvo/argumentos + workspace + origem da autorização. Um pedido para mostrar um link não concede permissão geral para escrever/apagar ficheiros.
- [ ] M1.2 Guardar uma autorização explícita ligada ao ID/versão do plano e à mensagem que a concedeu. **Retomar não é aprovar**: remover a promoção automática `authorized=True` de todo plano active. Na migração, autorização desconhecida permanece desconhecida; pedir confirmação, não inventá-la.
- [ ] M1.3 Fazer negação/cancelamento/restrições prevalecerem sobre nomes de ferramentas e sugestões do router. Não usar “contém create/write/file” como autoridade. Suportar cancelamento em mensagens compridas sem um teto semântico de 160 caracteres.
- [ ] M1.4 Classificar ferramentas no registo com efeito declarado; desconhecido não é read-only. Aplicar o mesmo contrato a skills personalizadas, conectores e materialização de HTML.
- [ ] M1.5 Não classificar shell como read-only só pelo executável. `find`, `awk`, `sed`, `env`, `xargs`, `sort` e subcomandos Git podem escrever/executar programas. Preferir ferramentas nativas de leitura com argumentos restritos; bash arbitrário precisa de autorização compatível e isolamento. Se existir parser de shell, testar sintaxe, flags, subcomandos e composição; não acrescentar apenas os exemplos desta auditoria à blacklist.
- [ ] M1.6 Resolver a chamada uma vez e executar exatamente o objeto/handler validado. Evitar duas resoluções semânticas potencialmente divergentes antes/depois da política.
- [ ] M1.7 Fazer o materializador gerar uma ação explícita com trace/recibo; não escrever só porque o modelo colocou HTML na resposta. Evitar caminhos de efeitos fora do dispatcher autorizado.
- [ ] M1.8 A UI deve mostrar a ação proposta, alvos e limites antes da aprovação; após cancelamento deve mostrar a revogação persistida, não apenas uma frase do modelo.

Regressões obrigatórias: pergunta → plano não autorizado → “obrigado”; “não cries um widget”; aprovação apenas para A seguida de chamada para B; alias; ferramenta desconhecida; comandos de escrita disfarçados de leitura; HTML sem aprovação; cancelamento seguido de retry; troca de workspace; restauro de plano legado sem prova de aprovação.

Gate: zero efeitos não autorizados nos casos críticos conhecidos e no conjunto reservado deste lote; bloquear **antes** do dispatcher. Testar a presença/ausência real do efeito, não só a string `blocked`. Não executar comandos destrutivos para provar o teste: usar simuladores/canários no sandbox.

Rollback: preservar contratos das ferramentas, manter um modo seguro que recusa efeitos sem capacidade demonstrável e reter decisões de autorização no audit log. Não voltar a abrir a permissão global para “compatibilidade”.

## M2 — Substituir contadores de trabalho por recibos verificados

Donos: [plans.py](C:/Users/nora/hmg-fu/hmgfu/plans.py), [session_plans.py](C:/Users/nora/hmg-fu/hmgfu/session_plans.py), dispatcher e armazenamento de sessões.

- [ ] M2.1 Definir um recibo por ação: ID, plano/etapa, ferramenta canónica, argumentos normalizados, autorização usada, início/fim, resultado, efeitos observados e pós-condições verificadas. `tool succeeded` não significa `task completed`.
- [ ] M2.2 Definir por etapa o resultado esperado: caminho e conteúdo/hash de ficheiro, widget e propriedades, consulta que devolveu os dados exigidos. Uma etapa de leitura também pode terminar legitimamente; não confundir read-only com “não é trabalho”.
- [ ] M2.3 `update_plan(done)` passa a pedir verificação da etapa. Remover `_turn_work > 0` como critério suficiente: uma leitura não pode certificar uma escrita, nem um ficheiro B certificar A.
- [ ] M2.4 Fazer `end_turn` e `update_plan` usar o mesmo verificador, com recibos consumidos pela etapa correspondente. O auto-complete não pode reutilizar a escrita de A para concluir B no fim do turno.
- [ ] M2.5 Estados distintos: proposed, approved, running, waiting, verifying, done, failed/partial, cancelled. Um conjunto done+failed não é done total. Definir transições permitidas e estados terminais.
- [ ] M2.6 Persistir plano/autorização/ação pretendida antes do efeito e o recibo após execução. Uma queda entre efeito e recibo produz estado “resultado desconhecido”; ao retomar, verificar o mundo antes de repetir a ação.
- [ ] M2.7 Adotar chaves de idempotência quando a ferramenta suporta; onde não suporta, detetar artefactos/estado preexistentes ou pedir revisão. Não prometer “exactly once” de processos externos só com SQLite.
- [ ] M2.8 Cancelamento revoga futuras ações e marca etapas incompletas; não reabre num “obrigado”, reconnect ou reinício. Definir separadamente o que pode interromper uma ferramenta já iniciada.

Regressões: memória → `done` de escrita; `write_file(b)` → `done(a)`; uma escrita → dois done; resposta do modelo anuncia conclusão sem ferramenta; falha parcial; crash antes/depois de escrever; timeout sem resultado; cancelamento durante espera; replay do mesmo recibo.

Gate: dois ficheiros pedidos existem com os conteúdos corretos antes do plano done; nenhum recibo sustenta duas etapas independentes; retomar o processo não duplica efeitos; UI e base apresentam o mesmo estado. Promover só após teste num processo realmente terminado/reiniciado, além do `close/reopen`.

## M3 — Completar a Fase 64: afirmações, não uma coleção crescente de padrões

Donos: [facts.py](C:/Users/nora/hmg-fu/hmgfu/facts.py), [fact_detect.py](C:/Users/nora/hmg-fu/hmgfu/fact_detect.py), [utterance.py](C:/Users/nora/hmg-fu/hmgfu/utterance.py), [slots.py](C:/Users/nora/hmg-fu/hmgfu/slots.py), `models`, `ingest`, `store`.

- [ ] M3.1 Representar uma afirmação com entidade/sujeito, relação, valor, polaridade, modalidade (real/hipotético/citado), âmbito, validade temporal, ID do episódio e trecho de origem. Guardar texto original imutável além da forma normalizada.
- [ ] M3.2 O extractor propõe 0..N afirmações; a admissão valida que **relação e valor estão no mesmo contexto**, não apenas algures na mensagem. Trecho existente é necessário, não suficiente. Sem evidência suficiente, conservar episódio como informação não confirmada ou pedir esclarecimento.
- [ ] M3.3 Tratar citações simples/duplas/tipográficas e contexto entre frases. A estrutura “para uma personagem fictícia” deve continuar a limitar a frase seguinte. A frase atual “desde 2023 moro em…” não é descartada só por conter data.
- [ ] M3.4 Resolver correções por entidade/relação/tempo/polaridade. “Último match ganha” não basta para “azul, não vermelho”, hipóteses comparadas ou histórico seguido de pergunta. Preservar conflitos explícitos até resolver.
- [ ] M3.5 Introduzir IDs de entidades de animais/pessoas, não mais um slot para cada espécie. Cão+gato é progresso; dois cães, dois irmãos e mudanças de posse precisam de cardinalidade geral. Manter os slots antigos como vistas de compatibilidade quando o resultado é inequívoco.
- [ ] M3.6 Atualizações de URL vinculam-se ao objeto referido. A palavra genérica `link` dentro de “recipe link” não autoriza sobrescrever a ligação do carro. Referente ambíguo requer resolução contextual ou pergunta.
- [ ] M3.7 Retração/correção invalida a afirmação correspondente, não o episódio inteiro que também contém outros factos úteis. Resumos/macros guardam dependências dos factos que derivam e são recalculados/invalidados sem apagar história legítima.
- [ ] M3.8 Aplicar episódio+afirmações+histórico/proveniência numa transação ou numa sequência recuperável explicitamente modelada. Não confirmar memória antes de a gravação durável terminar.
- [ ] M3.9 Rever ingestão/deduplicação: a frase declarativa “When visiting the clinic, park behind the bakery” foi marcada `_question` e excluída dos dois braços de retrieval. A fusão por similaridade não deve apagar detalhes distintos nem mudar o conteúdo sem reconstruir as suas representações e relações.

Regressões mínimas: todos os casos antigos; citação com aspas simples; hipótese em duas frases; mãe Ana + cor âmbar com mapper a trocar a ligação; data atual PT/EN; correção dentro da mesma frase; dois cães; gato preservado ao retirar cão; pet legado versus cão novo; links de dois assuntos; episódio com dois factos dos quais só um é retirado; negação e instrução de navegação não interrogativa.

Gate proposto para promoção (não resultado já obtido): zero corrupções nos casos críticos conhecidos; ≥200 mensagens multilingues reservadas, com precisão de escrita e recall separados; apontar ≥98% de precisão e ≥90% de cobertura de afirmações admissíveis, reportando intervalo de confiança e por categoria. Se não alcançar, não converter inferência em canon para melhorar artificialmente recall. Rever estes limiares antes de ver os números.

Migração: snapshot consistente; importação para schema novo numa cópia; inventário de factos sem fonte; campo `legacy_unverified` quando não existe prova, sem fabricar source span. Não inferir que `pet.name` é cão sem evidência. Reconciliar duplicados/conflitos e comparar vistas antigas/novas antes de promover. Guardar versão antiga recuperável e histórico de decisões; limpeza da base real exige execução explicitamente autorizada.

## M4 — Um contrato de memória em todos os pontos de entrada

Reutilizar `facts`, `retrieve`, `chat` e `agent`; expor uma fachada de serviço sobre estas responsabilidades, não um segundo sistema de memória.

- [ ] M4.1 Fazer API chat, agent chat, WS, CLI e ingest chamar a mesma admissão de episódios/afirmações. A Fase 69 adicionou escrita no chat legado, mas este ainda não garante a mesma leitura canónica, invalidação e source linking do caminho agent.
- [ ] M4.2 Query devolve um pacote de evidência tipado: afirmações válidas, episódios citáveis, contexto temporal, inferências marcadas e IDs/fontes. O mesmo pacote alimenta resposta normal, `memory_search`, zoom/timeline, recall de plano e UI.
- [ ] M4.3 Não apresentar resumo/entidade extraídos pelo nano como prova da verdade. Manter resumo como índice/compressão e permitir abrir o original. Se o trecho foi truncado, não afirmar que contém a prova fora do limite.
- [ ] M4.4 Vistas “atual” e “histórica” explícitas; vazio e falha de retrieval mantêm canon disponível e reportam a limitação. Não fazer leitura “dry” alterar workspace, migrações ou a semântica do próximo turno.
- [ ] M4.5 Retirar a implementação duplicada de chat só depois de testes de paridade; conservar rotas/CLI como adaptadores com depreciação documentada.

Gate: o mesmo episódio dá as mesmas afirmações/versões/retrações em todos os pontos de entrada; as mesmas perguntas recebem os mesmos IDs elegíveis, respeitadas diferenças declaradas do endpoint. Histórico continua consultável sem contaminar “atualmente”.

## M5 — Confirmar precisamente o que aconteceu

Donos: [saydo.py](C:/Users/nora/hmg-fu/hmgfu/saydo.py), [grounding.py](C:/Users/nora/hmg-fu/hmgfu/grounding.py), [agent.py](C:/Users/nora/hmg-fu/hmgfu/agent.py), contexto de evidência e UI.

- [ ] M5.1 Trocar a correspondência apenas por classe remove/create/update/memory por ligação entre alegação e recibo/facto: alvo, relação, valor e resultado. Uma escrita de cor não prova atualização de URL; criar ficheiro não prova widget.
- [ ] M5.2 Gravar o episódio primeiro; só depois dizer “registei”. `episode=True` antecipado não deve certificar afirmações que falharam nem detalhes que a pessoa não afirmou.
- [ ] M5.3 Verificar a resposta final depois de **todos** os retries/transformações; se grounding gera uma resposta nova, verificar novamente alegações de execução. Evitar ciclos ilimitados: um orçamento pequeno de reparação e fallback honesto.
- [ ] M5.4 Avaliar entidade, unidade, tempo, negação e relação. Números pequenos não são sempre numeração de listas; o mesmo número de outra cidade não é evidência. Um verificador por modelo é opção experimental, não solução pressuposta: deve ser medido com falsos positivos, abstenção e latência.
- [ ] M5.5 Distinguir “lembrado no episódio”, “facto confirmado no registo” e “inferência”. Não anunciar canon perfeito quando apenas um episódio foi guardado.
- [ ] M5.6 Remover confirmação falsa da resposta; não acrescentar uma correção genérica que contradiz também uma escrita legítima. O estado verificável deve informar a composição da resposta, em vez de a resposta ditar o estado.
- [ ] M5.7 UI apresenta fonte/recibo e resultado da verificação; feedback semântico não deve chamar-se garantia universal. Preservar erros/reparações no histórico, sem duplicar cartões inúteis.

Gate: alegações erradas com transação da mesma classe mas alvo diferente são rejeitadas; ações falhadas/bloqueadas nunca têm etiqueta de execução concluída; nova resposta após retry não contorna o verificador; taxa de falsa confirmação medida por alvo, não só por verbo.

## M6 — Medir se Fu acrescenta valor, sem confundir camadas

### Desenho do benchmark

- [ ] M6.1 Escrita: avaliar afirmações esperadas e inesperadas, cobertura por mensagem, entidade/polaridade/tempo/fonte, preservação após reabertura e rollback de correções. Não medir só strings na resposta.
- [ ] M6.2 Ingestão: medir factos conservados, fusões incorretas, classificação de perguntas, invalidações colaterais e validade dos IDs gold depois da ingestão. Se o ponto esperado foi excluído, atribuir a falha à elegibilidade em vez de ao ranker.
- [ ] M6.3 Retrieval: ID gold, Hit@1/5/10, MRR/nDCG, taxa de evidência obsoleta, cobertura de múltiplas evidências e recall de restrições. Fixar o mesmo pool elegível, orçamento de tokens, embedding, datas e ordenação experimental.
- [ ] M6.4 Leitura: fornecer contextos congelados iguais a cada modelo; avaliar resposta correta, abstenção e referência à fonte. Comparar com contexto oracle apenas como diagnóstico do leitor, não como resultado de retrieval.
- [ ] M6.5 Ações: estado real depois de cada turno + caminho de execução exigido. Ficheiro correto, conteúdo correto, nenhum efeito colateral, cancelamento e retomada; não contar um simples nome de ferramenta como realização do objetivo.
- [ ] M6.6 Segurança: escrever informação adversarial sintética, provocar recall/ação, retirar a informação e repetir. Medir também dano a conhecimento legítimo ao lado do conteúdo retirado.

### Braços e controlos

1. Sem memória persistente, janela recente fixa.
2. Episódios + cosine, sem canon.
3. Episódios + cosine + mesmo ledger/verificador.
4. Mesmo sistema do braço 3 + componente Fu específico.
5. Ablacões individuais de temporalidade, expansão, densidade, dreams e aprendizagem, só quando os braços anteriores forem estáveis.

Janelas 0/3/6 devem ser cruzadas com os braços relevantes, em ordem balanceada, com pelo menos três repetições dos casos estocásticos. Não comparar um braço carregado com grader/dreams a outro sem esses custos. Cada episódio tem base/workspace independentes; conhecimento global não vaza entre casos.

### Corpus, métricas e decisão

- [ ] M6.7 Aproveitar os harnesses externos já existentes no projeto. Executar uma amostra de smoke claramente identificada, depois os 500 casos do [LongMemEval](https://arxiv.org/abs/2410.10813), separando oracle das condições com histórico completo e reportando as cinco capacidades. Escolher e congelar a versão dos dados antes de correr.
- [ ] M6.8 Para ações, adotar verificação de estado e trajetória inspirada no [BFCL V3](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html), com adaptações identificadas; não chamar ao nosso conjunto sintético um score oficial BFCL.
- [ ] M6.9 O avaliador não importa `is_user_grounded` ou o detector de sucesso do próprio runtime como verdade de referência. Usar asserts de estado, labels de fontes e juiz independente/humano nos itens semânticos; auditar amostra das decisões.
- [ ] M6.10 Reportar latências p50/p95 por etapa e total, chamadas/modelo, tokens, RAM/VRAM, erros de provider e custo de ingestão/reconstrução. Guardar resultados por item e diferenças emparelhadas com intervalos de confiança; não tratar zero falhas em seis casos como garantia.
- [ ] M6.11 Pré-registar um ganho mínimo de interesse antes da execução. Proposta: promover Fu apenas com ganho repetível em qualidade no domínio escolhido, sem regressão nos testes críticos e dentro de um teto de latência acordado; reportar também ganhos nulos/negativos. Não escolher o domínio ou a métrica depois de ver o vencedor.

O ensaio desta auditoria, **19/20 para Fu e 19/20 para cosine**, não justifica promover ou apagar Fu. A frase perdida foi excluída como pergunta; houve apenas 23 pontos após dedup. É evidência de funcionamento básico, não um benchmark exigente de memória longa. O estudo [Does Memory Need Graphs?](https://aclanthology.org/2026.acl-long.1232/) reforça a necessidade de comparações controladas de construção e recuperação, não uma escolha automática a favor ou contra grafos.

## M7 — Fechar operação, interfaces e manutenção

- [ ] M7.1 `AgentEngine.close()` idempotente fecha todos os stores/providers, interrompe/aguarda trabalho de fundo dentro de limites e limpa runtime/callbacks. `try/finally` também limpa o estado de turno após falhas.
- [ ] M7.2 Documentar os donos do estado e a política de concorrência: worker de chat, endpoints, settings e dream. Usar snapshots/serialização/coordenador de transação onde necessário; não resolver tudo com um lock global mantido durante chamadas longas ao modelo.
- [ ] M7.3 Capturar configuração/workspace por turno/plano. Mudanças de settings aplicam-se a operações novas ou exigem migração explícita, não alteram o alvo de uma escrita em curso.
- [ ] M7.4 Health e UI mostram os modelos resolvidos e features efetivamente ativas. Alinhar README, AGENTS, PROJECT_ID e teoria vigente: o contrato v2 de cosine e o pipeline Fu carregado não podem continuar descritos como se fossem a mesma implementação.
- [ ] M7.5 Testar UI com navegador: loading/error/empty/blocked/failed/partial/cancelled, feedback reparado, reconexão, histórico e artefactos. A auditoria atual testou reducers, não disposição visual completa.
- [ ] M7.6 Acrescentar instalação reprodutível/dependências fixadas e checks estáticos ao processo. Ruff ausente deve aparecer como “não executado”, não “passou”.
- [ ] M7.7 Antes de partilhar via rede/tailnet, definir autenticação, isolamento de dados/workspaces e política de ferramentas. Não promover o protótipo local para outro modelo de ameaça sem essa revisão.

Gate: testes de crash/cancel/settings concorrentes não escrevem no workspace errado nem deixam planos fantasmas; execução longa tem recursos limitados e shutdown limpo; utilizador vê o mesmo estado que a base/recibos.

## Remover, consolidar ou manter

| Componente | Decisão proposta | Condição |
|---|---|---|
| `authority.py` | Manter e aprofundar | É a costura correta; precisa de âmbito e argumentos, não outro guard paralelo. |
| Listas read-only de shell | Retirar como prova suficiente | Substituir por operações restritas ou capacidades para shell. |
| `_turn_work`/auto-complete por nome de ferramenta | Retirar como certificação | Recibos por etapa e pós-condições primeiro. |
| `pet.dog.name`/`pet.cat.name` | Manter como adaptação de compatibilidade | Não proliferar espécies como substituto de entidades. |
| Regex de afirmações e say-do | Manter onde úteis para casos simples/observabilidade | Não constituem sozinhas a fonte de verdade nem autorização. |
| `is_user_grounded` nos benchmarks | Retirar como oráculo factual | Entidades ou comprimento de texto não provam grounding. |
| Chat legado duplicado | Descontinuar internals gradualmente | Paridade e adaptadores públicos preservados. |
| Materializador HTML | Manter a capacidade, retirar escrita implícita | Converter em ação autorizada e rastreável. |
| Grafos/Fu/sonhos/aprendizagem | Manter como componentes experimentais | Separar contribuição e custo; promover só com evidência. |
| Scripts de auditoria | Arquivar por versão e consolidar utilidades | Preservar fixtures/counterexamples, sem copiar heurísticas do produto para o juiz. |

## Regra de entrega para cada lote

- [ ] Antes: atualizar ROADMAP/ADR com alteração de contrato, consumidores e critérios de aceitação.
- [ ] Durante: reproduzir → corrigir no dono → testar variantes não usadas na implementação → verificar consumidores/estado/UI → registar resultado e limites.
- [ ] Depois: suite completa, contratos, smoke natural em scratch, inspeção do estado real, documentação/configuração e estratégia de rollback. Checkbox só fecha com evidência ligada ao commit.
- [ ] Se uma garantia não foi provada, registar “parcial” ou “não testada”; não ajustar a descrição de sucesso para encaixar no resultado.

**Sugestão de próximo trabalho:** implementar M0 e M1 primeiro para permitir experimentar com ações em segurança, enquanto M3 organiza a memória factual. Só depois confiar em execução autónoma longa e gastar muitas horas a otimizar Fu. Esta ordem decorre dos testes; não exige trocar de modelo nem desistir do conceito.
