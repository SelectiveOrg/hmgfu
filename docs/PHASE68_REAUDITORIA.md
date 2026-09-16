# Fase 68 — Reanálise crítica depois do trabalho de Claude

Data: 5 de setembro de 2026. **Relatório histórico da primeira ronda, sobre `04fc9ba`.** Durante a pausa, Claude publicou a Fase 69 (`8b675a9`) e corrigiu vários problemas abaixo. A [revalidação independente atual](C:/Users/nora/hmg-fu/docs/PHASE69_REVALIDACAO_INDEPENDENTE.md) distingue o que ficou resolvido dos problemas remanescentes; não interpretar a lista histórica como defeitos ainda presentes. Âmbito: testar, desafiar, registar, pesquisar e propor; **não implementar correções de produção**. O [plano detalhado](C:/Users/nora/hmg-fu/docs/PHASE68_PLANO_MELHORIAS.md) está atualizado para o código corrente, sem repetir correções já feitas.

## 1. Conclusão

Claude fez melhorias reais, mas a confiança transmitida pelas respostas e pelos benchmarks ainda excede as garantias do código. A memória episódica já consegue recuperar informação útil depois de reabrir o motor e começar outra sessão. Contudo, a memória considerada verdadeira pode guardar a pessoa errada, a preferência errada ou substituir uma ligação de outro assunto. O sistema de ações também pode declarar uma etapa concluída sem criar o ficheiro e manter um plano ativo depois de o utilizador o cancelar.

O problema prioritário não é falta de mais fórmulas, mais agentes ou um modelo maior. É a falta de contratos únicos entre **evidência → facto → autorização → execução → verificação → resposta**. Existem várias heurísticas que acertam nas frases usadas para desenvolvê-las, mas não garantem a mesma propriedade noutros caminhos.

O conceito HMG-Fu merece continuar a ser investigado. Estes resultados não demonstram uma solução geral para memória de AGI, nem permitem concluir que a representação relacional é inútil. A contribuição específica de Fu tem de ser isolada da qualidade do embedding, do registo canónico, da janela recente e do modelo que responde.

## 2. O que foi realmente verificado

| Verificação | Resultado e alcance |
|---|---|
| Suite existente | **417 testes passaram**, 214,45 s; testes sem Ollama. Não significa que os contratos ausentes estejam cobertos. |
| Diagnóstico determinístico novo | **56 verificações: 12 satisfeitas, 44 não satisfeitas**. Casos adversariais selecionados e controlos positivos; não é uma taxa de acerto da população nem 44 bugs independentes. |
| Conversa natural | **12 turnos**, modelos locais reais; 371,99 s no total, incluindo preparação/reabertura. |
| Ações e aprovações | **8 turnos**, janelas 3 e 0, ficheiros isolados e reabertura; 422,35 s. Um turno sofreu falha do provider. |
| UI, comportamento de estado | **4 contratos não satisfeitos**, executando o reducer real de eventos e a reconstrução do histórico em Node. Não é teste visual de navegador. |
| Retrieval independente | Resultado do ensaio de 20 perguntas registado na secção 5. |
| Integridade da base real | SQLite `integrity_check=ok`; 1.656 pontos, 1.036 ativos; 882 pontos ativos de origem assistant. Dez factos canónicos, nove sem `source_turn_id`. Consulta só de leitura. |
| Cobertura | Inventário de 204 artefactos rastreados: 59 módulos Python da aplicação, 50 testes, 50 scripts, 27 recursos web e 18 documentos. AST, símbolos e SHA256 registados. |

Modelos efetivos herdados das definições persistidas: `gemma4:12b`, `qwen2.5:1.5b-instruct`, `bge-m3`. Os testes naturais desligam grader, aprendizagem, dreams e regulator, limitam o orçamento de iterações e bloqueiam ferramentas externas/shell/skills. O timeout configurado por chamada é 60 s; retries e múltiplas chamadas tornam o turno mais longo. Não se deve interpretar isto como uma medição idêntica a todas as definições de produção.

O servidor da aplicação em 8777 estava parado; Ollama em 11434 estava disponível. Usei o motor real diretamente, não o ecrã de Claude nem a UI em produção. “Reinício” nesta auditoria significa fechar os recursos e instanciar outro motor sobre a mesma base; **não** simular queda abrupta do processo. O teste de crash verdadeiro está no plano.

Artefactos novos de reprodução:

- [Contratos e inventário](C:/Users/nora/hmg-fu/scripts/audit_phase68_contracts.py) → [JSON](C:/Users/nora/hmg-fu/outputs/phase68_contracts.json).
- [Conversas e benchmark](C:/Users/nora/hmg-fu/scripts/audit_phase68_live.py) → [memória](C:/Users/nora/hmg-fu/outputs/phase68_live_memory.json), [ações](C:/Users/nora/hmg-fu/outputs/phase68_live_actions.json), [retrieval](C:/Users/nora/hmg-fu/outputs/phase68_live_retrieval.json).
- [Contratos da UI](C:/Users/nora/hmg-fu/scripts/audit_phase68_ui.cjs) → [JSON](C:/Users/nora/hmg-fu/outputs/phase68_ui_contracts.json).

Os resultados e bases temporárias estão em diretórios locais ignorados pelo Git. Atenção à proveniência experimental: os scripts antigos escrevem em caminhos fixos; `phase68_contracts.json` e `phase68_ui_contracts.json` foram reutilizados nas reexecuções da Fase 69 e já não representam o snapshot inicial 12/56 e 0/4. As observações históricas são preservadas neste relatório; os resultados atuais têm caminhos `phase69_reaudit_*` no relatório novo. Nenhum dado pessoal foi enviado aos sites consultados. Nenhuma correção, limpeza de dados ou remoção de código de produção foi feita por esta auditoria.

## 3. Melhorias de Claude que se confirmaram

1. O mapper já rejeita um valor que não existe no texto. Corrige o caso anterior de uma resposta do nano inventar um nome ausente.
2. Uma mensagem em inglês pode gravar vários factos de slots diferentes. Nome, cidade e cão foram gravados no mesmo turno real.
3. Pedidos educados como “Could you remember…” já funcionam.
4. A eliminação por seletor já limpa o slot canónico sem repetir o nome do animal; falta preservar outras entidades e retirar a evidência antiga da leitura atual.
5. `Rust` já não elimina `Trust` por correspondência de substring. Falta limitar a operação ao atributo e entidade corretos.
6. A injeção normal passou a preferir conteúdo original do utilizador; perguntas deixaram de competir diretamente como respostas na seleção normal.
7. Há planos persistentes por sessão, janela recente configurável e alguns bloqueios antes de ferramentas. São bases úteis, ainda incompletas.
8. O benchmark passou a distinguir CONTEXT de retrieval e ganhou a opção sem canon. Dados pessoais/resultados temporários foram excluídos do Git.

Não classifico estas alterações como trabalho inútil. A crítica é à generalidade das garantias e aos critérios usados para declarar a fase concluída.

## 4. Achados prioritários, com causa e reprodução

P1 = falha demonstrada de integridade/autorização/conclusão importante para este protótipo. P2 = defeito de alcance menor ou risco ainda sem reprodução operacional completa. Os testes com provider programado exercitam o código real do motor e isolam o contrato; não estimam a frequência com que Gemma produzirá cada chamada.

### F01 — P1: o texto gravado não representa necessariamente o facto que foi dito

Em [fact_detect.py](C:/Users/nora/hmg-fu/hmgfu/fact_detect.py:117), a deteção por fragmentos e a deduplicação por chave perdem a relação entre cláusulas. Em [facts.py](C:/Users/nora/hmg-fu/hmgfu/facts.py:70), o veto interrogativo aplica-se à mensagem inteira. Em [slots.py](C:/Users/nora/hmg-fu/hmgfu/slots.py:188), encontrar o valor no texto não prova o sujeito nem o predicado.

Reproduções naturais, com estado da base inspecionado:

| O que foi dito | Resposta | Estado persistido |
|---|---|---|
| “My friend says ‘my name is Oscar’… his name, not mine.” | Compreende que Oscar é o amigo, não a utilizadora. | Substitui `identity.name=Nadia Costa` por **Oscar**. |
| Vermelho, depois azul, com a segunda cláusula a corrigir a primeira | Diz que registou azul. | Guarda **red**. |
| “I live in Chimoio. What do you know about that city?” | Responde sobre a cidade. | Mantém **Lichinga**, a cidade anterior. |
| “If my favorite color is violet… this is hypothetical.” | Trata violeta como preferência mencionada. | Guarda **violet** como facto atual. |
| Cor âmbar e chá de hibisco, em português | Promete guardar. | Nenhum dos dois slots é criado; a memória episódica guarda o texto. |

O teste determinístico também aceita `family.mother_name=âmbar` quando o nano devolve essa relação para uma frase sobre cor: o valor existe no texto, mas a relação está errada. “black and white” é truncado para “black”. Factos passados podem ser tratados como atuais.

Caminho e severidade: acontece sincronamente em `agent_chat → facts.apply_all`, antes de compor a resposta; o lock de turno não protege contra erro semântico. Os casos de nome/cor foram observados com o modelo local real. Não é um problema resolvido apenas aumentando contexto ou mudando o ranking.

### F02 — P1: correção e esquecimento não respeitam entidade, atributo e tipo de conhecimento

[facts.py](C:/Users/nora/hmg-fu/hmgfu/facts.py:99) escolhe o único slot compatível com o **tipo do valor** para certas atualizações. Com um URL de carro guardado, “Here is the new recipe: https://example.test/soup” substitui o link do carro. Reproduzido deterministicamente e nas duas conversas reais, janelas 3 e 0.

Existe um só `pet.name`. “My cat is Mica and my dog is Teca” guarda apenas Mica; retirar o cão pode apagar esse slot do gato. O teste simples `pet.name=None` passa, mas o requisito completo “retirar cão, preservar gato” falha. Por isso não agreguei esses checks parciais como uma percentagem de memória correta.

[superseded_values](C:/Users/nora/hmg-fu/hmgfu/facts.py:196) perde a pista do valor retirado quando a chave deixa de existir; o ponto episódico antigo continua ativo. [supersede_stale_nodes](C:/Users/nora/hmg-fu/hmgfu/facts.py:216) ainda opera por palavra antiga: corrigir a cor favorita de azul para verde pode retirar o ponto independente “o meu carro é azul”. A correção Rust/Trust resolveu a fronteira da palavra, não a fronteira da afirmação.

O recall real após retirar o cão respondeu corretamente “sem cão, gata Mica” graças aos episódios. Esse sucesso não corrige o estado canónico incompleto nem garante que outro caminho não recupere a versão antiga.

### F03 — P1: há caminhos que contornam a autorização de ações

Em [tool_loop.py](C:/Users/nora/hmg-fu/hmgfu/tool_loop.py:187), a classificação de efeitos acontece antes da resolução flexível do nome em [toolsys.py](C:/Users/nora/hmg-fu/hmgfu/toolsys.py:163).

Reproduções de turno completo:

- `create_widge` não pertence à lista de efeitos; é depois resolvido para `create_widget` e cria um widget sem aprovação. O resultado confirma `_rerouted` e `ok=true`.
- Numa pergunta sobre vulcões, o modelo chama `plan_task` e depois `create_widget`. Um plano inventado pelo próprio modelo abre o caminho para executar uma ação não pedida. A proteção específica para sugestões não cobre esta pergunta normal.
- Uma resposta HTML a “talvez criar mais tarde, espera confirmação” cria `app.html` pelo materializador, com **tool trace vazio**, em [widgets.py](C:/Users/nora/hmg-fu/hmgfu/widgets.py:135). A chamada está depois dos verificadores em [agent.py](C:/Users/nora/hmg-fu/hmgfu/agent.py:298).
- A lista de efeitos em `toolsys` omite `bash`; o teste mostra a chamada a chegar ao dispatcher sem confirmação. O comando foi interceptado por um mock; **não executei shell destrutivo**. Skills personalizadas também carecem de classificação explícita de efeitos.

O alcance demonstrado é dentro do processo/local workspace. Não alego invasão remota. O problema é uma fronteira de autorização interna que pode ser atravessada por uma saída de modelo.

### F04 — P1: “concluído” e “cancelado” não correspondem ao estado real do plano

[begin_turn](C:/Users/nora/hmg-fu/hmgfu/session_plans.py:128) interpreta a negação enquanto existe uma proposta, mas retoma um plano ativo mesmo perante cancelamento. [end_turn](C:/Users/nora/hmg-fu/hmgfu/session_plans.py:154) usa qualquer ferramenta bem-sucedida como evidência para concluir a etapa ativa. [update_plan](C:/Users/nora/hmg-fu/hmgfu/plans.py:93) aceita `done` declarado pelo modelo. `finalize_status` considera um plano com todas as etapas falhadas como `done`.

Prova real particularmente clara: pedi dois ficheiros com o conteúdo literal `MEMORY-68`. O modelo procurou esse texto na memória em vez de o escrever; **nenhum ficheiro foi criado**. Depois de reabrir o motor, pedi cancelamento. A resposta terminou com “The task has been cancelled”, mas a base continuou com o plano **active**, marcou a criação do primeiro ficheiro **done** e ativou a segunda etapa. A única ferramenta usada foi `memory_search`.

O teste não demonstra escrita depois do cancelamento: os ficheiros continuaram ausentes. Demonstra cancelamento não persistido, continuação de trabalho de leitura e conclusão falsa de uma escrita. Há ainda risco não testado de repetição após crash: as alterações de etapas são persistidas no fim do turno, sem recibos duráveis/idempotência por ação.

### F05 — P1: “say-do” não liga cada alegação à transação correspondente

Em [saydo.py](C:/Users/nora/hmg-fu/hmgfu/saydo.py:58), basta haver alguma transação para validar uma alegação de execução. Num turno completo, gravar a preferência de cor deixou passar “I've removed your dog and deleted the report.” Sem retirar cão nem apagar relatório.

Outros checks mostram que uma tentativa falhada pode satisfazer a noção de “houve ação”; construções como “Your link has been updated”, passivas e “Já memorizei…” escapam aos padrões. Na conversa real, simples confirmações de memória já gravada geraram propostas artificiais terminadas com “Shall I go ahead?”.

O próprio “self-grade” não é uma certificação independente. Não deve servir como oráculo de benchmark nem prova de execução apresentada ao utilizador.

### F06 — P1/P2: a verificação de evidência é lexical e não cobre a resposta final

P1 de ordenação: [agent.py](C:/Users/nora/hmg-fu/hmgfu/agent.py:267) verifica grounding **antes** do retry de say-do. Um teste completo começa com uma intenção de leitura, faz o retry, recebe `memory_timeline` e termina com “The temperature is 73°C.” sem prova nem aviso. A nova resposta não volta ao verificador. Existem transformações e materialização de artefactos depois dessa fase.

P2 de alcance semântico: [grounding.py](C:/Users/nora/hmg-fu/hmgfu/grounding.py:29) extrai o número mas perde a unidade. “26% de humidade” valida “26°C”; temperatura de Lisboa valida a de Valencia; números pequenos são ignorados como se fossem sempre contadores. Nomes não são verificados — limitação assumida no módulo, não alegação de funcionalidade implementada. A designação “AgentLTL-style” não equivale a implementar as garantias formais desse trabalho.

### F07 — P1: proveniência e política de verdade continuam diferentes entre caminhos

A injeção normal melhorou, mas [memory_search](C:/Users/nora/hmg-fu/hmgfu/toolsys.py:279) e [step_recall](C:/Users/nora/hmg-fu/hmgfu/plans.py:139) ainda apresentam `summary` gerado como memória factual. Um ponto cujo conteúdo original não contém um nome devolveu uma mãe inventada apenas no resumo, pelos dois caminhos. História e painéis também usam resumos. É preciso preservar episódio original e distinguir derivação, não proibir resumos úteis.

A chamada legada `engine.chat` não grava o ledger: reproduzido por turno com provider programado. As rotas `/api/chat`, `/api/ingest`, `/api/retrieve` e a CLI têm contratos diferentes dos de `agent_chat`. Há ainda um caso de erro/empty: pesquisa bem-sucedida com zero resultados omite canon, apesar de o caminho de exceção o devolver.

### F08 — P1/P2: migração e eliminação não respeitam todo o ciclo de vida

P1: em [hygiene.py](C:/Users/nora/hmg-fu/hmgfu/hygiene.py:155), a migração de regras relê um episódio antigo e restaura “Always use read_file…” depois de o utilizador a retirar. Reproduzido com a mesma rotina chamada no arranque, sem LLM.

P2: apagar uma sessão em [sessions.py](C:/Users/nora/hmg-fu/hmgfu/sessions.py:97) deixa o plano em `session_plans`. Regras temporárias/condicionais ainda são aproximadas por sobreposição lexical e um valor por ferramenta. A migração deve ser versionada e respeitar os eventos de revogação; não inferir novamente autorização a cada arranque.

### F09 — P2: argumentos de ferramentas e UI dão sinais incorretos

[deixis.py](C:/Users/nora/hmg-fu/hmgfu/deixis.py:29) transforma “Lisbon weather tomorrow”, com “Weather for Lisbon tomorrow”, numa pesquisa que acrescenta **Quelimane e a data de hoje**. A cidade explícita e a referência temporal não são preservadas. Um widget que já contenha um dos valores pedidos pode deixar de receber os restantes.

Em [events.jsx](C:/Users/nora/hmg-fu/web/app/events.jsx), os eventos `grounding` e `saydo` não originam feedback; ao restaurar o histórico, uma ferramenta bloqueada aparece como sucesso e o self-grade de say-do desaparece. O teste executou o reducer real, não um substituto. A classificação visual de etapas falhadas também merece alinhar-se com a máquina de estados.

### F10 — P1 para a validade experimental: o avaliador consegue aprovar falhas

[bench_tool_precision.py](C:/Users/nora/hmg-fu/scripts/bench_tool_precision.py:80) aprovou um caso com pesquisa falhada e resposta “I cannot get the weather.”, marcando `expect_ok=true` e `answer_grounded=true`. Verifica a presença da chamada e a ausência de números inventados, não a obtenção da resposta exigida.

[bench_recall_truth.py](C:/Users/nora/hmg-fu/scripts/bench_recall_truth.py:53) ainda conta “Java was my old preference” e “Java is not my favorite language” como presença da verdade esperada. O filtro de negação foi melhorado, mas não avalia a afirmação inteira.

`is_user_grounded` em [taxonomy.py](C:/Users/nora/hmg-fu/hmgfu/taxonomy.py:47) aprova um ponto assistant fabricado com um número. A métrica chamada “precision” não mede relevância para a pergunta, nem comprova origem factual. `bench_tool_precision` importa o próprio verificador que pretende avaliar, criando circularidade. Os conjuntos pequenos foram reutilizados em sucessivas correções; faltam casos reservados, independência entre episódios e múltiplas amostras.

## 5. Resultados de memória: separar recordar, gravar e provar

### Conversa natural

Depois de fechar o primeiro motor e iniciar uma sessão sem histórico recente, o sistema respondeu corretamente aos **seis elementos pedidos**: nome, cidade, cão, cor, bebida e música. Cor e bebida vieram de episódios apesar de não terem sido gravadas no ledger. Também conseguiu recordar a retirada do cão preservando verbalmente a gata.

Isto demonstra utilidade da memória persistida. Também demonstra por que uma resposta correta, sozinha, pode esconder um erro no armazenamento. Uma avaliação honesta inspeciona tanto o estado como a resposta e testa a mesma pergunta depois de correções, esquecimento e reinícios.

### Retrieval com resposta de referência independente

O ensaio terminou: **Fu e cosine empataram, ambos Hit@1/5/10 = 19/20 e MRR = 0,95**. Foram 20 perguntas novas, factos sintéticos e distratores, embeddings reais e comparação pelos IDs esperados, sem inserir respostas do ledger. As 50 tentativas de ingestão produziram apenas 23 pontos devido a deduplicação; os 20 IDs de referência são distintos. A mesma pergunta falhou nos dois braços. A frase perdida, “When visiting the clinic, park behind the bakery”, foi confirmada em SQLite como `message`/`_question`: ficou fora do pool antes do ranking. A comparação é entre pipeline Fu e ordenação por cosine; é um conjunto pequeno e fácil, não um benchmark externo nem uma demonstração geral de superioridade.

### Como ler as execuções anteriores de Claude

Os artefactos da Fase 67 registam say-do **5/6 com janela 3** e **6/6 com janela 0**, truth **16/17** e tools **7/8**. São registos existentes inspecionados, não esses mesmos ensaios repetidos nesta fase. Em especial:

- Um acerto de CONTEXT pode vir da injeção canónica e não do retrieval. O nome agora é mais honesto, mas a interpretação precisa manter essa distinção.
- O benchmark say-do partilha uma cópia de base entre casos; reinicializar a sessão não elimina contaminação de memórias/regras globais.
- Existirem três ficheiros não prova conteúdo correto, nem que cada etapa declarada corresponde ao artefacto.
- Uma amostra de seis episódios não demonstra que janela zero é melhor. Modelo, ordem, recalls e retries também variam.
- O relato de Claude já reconhece a lacuna de `update_plan(done)` em 67.16. A auditoria confirma-a e mostra que o auto-complete tem uma lacuna independente.

## 6. Cobertura transversal e riscos ainda não demonstrados em carga

Fiz inventário/AST de toda a árvore selecionada, leitura direta das alterações de produção das fases novas e seguimento dos seus chamadores, armazenamento, rotas, UI, testes e avaliadores. Os módulos estáveis tiveram varrimentos por preocupação; não afirmo leitura manual integral de todas as linhas dos 204 ficheiros. Recursos vendorizados/gerados receberam inventário e referências, sem auditoria interna ou visual.

| Preocupação | Evidência / limite |
|---|---|
| Concorrência | `agent_chat` tem lock global e liberta-o em `finally`: não há fundamento para afirmar corrida entre dois turnos desse método. Contudo, rotas usam workers AnyIO e dream usa uma thread daemon distinta; ingest/retrieve/settings não partilham esse lock. Há leitores diretos de `graph.points.values()` fora dos snapshots protegidos. Risco P2; não injetei um interleaving para demonstrar corrupção. |
| Recursos | Lifespan da API fecha graph/client, mas não todos os stores SQLite nem coordena o dream thread. `SessionPlanStore` não tem `close`. Risco P2 em shutdown/reabertura; não medi fuga de handles em carga. |
| Estado/configuração | Workspace de ferramentas é global e pode ser alterado por definições/retrieve durante uma execução; falta snapshot imutável por turno/plano. Health e documentação ainda podem anunciar `nomic-embed-text` quando o modelo persistido é bge-m3. |
| Atomicidade | Factos são aplicados antes da ingestão do episódio e confirmados separadamente. Falha posterior pode deixar facto sem origem/turno. A limpeza de `_turn_session/_turn_emit` está só no fim normal do método; o lock externo não limpa estes campos numa exceção. Falta teste de fault injection. |
| Matemática/limites | Suite matemática passou; inspeção de clamps, propagação, datas e fronteiras não encontrou nova falha numérica reproduzida nesta ronda. A superioridade dos pesos/arestas continua hipótese empírica, não consequência das fórmulas. |
| Segurança/proveniência | Fronteiras de efeito/alias/materialização reproduzidas. Sem testes contra serviços reais, credenciais, shell destrutivo ou rede externa. Autenticação torna-se requisito antes de exposição remota; não a tratei como falha de um protótipo estritamente local por si só. |
| Erro/vazio/restauro | Contratos de pesquisa vazia, migração, falhas de ferramentas, cancelamento e histórico/UI executados. Provider vazio registado como falha ambiental/modelo, não prova de um defeito de retrieval. |
| Fecho da revisão | Segunda passagem pelos mesmos contratos e caminhos de erro não acrescentou outro achado confirmado; os riscos acima ficam explicitamente em aberto. Não equivale a prova de ausência de bugs. |

`compileall` e `git diff --check` foram executados. Ruff não está instalado nesta venv; não reporto lint limpo. Não foi feito benchmark de carga longa, auditoria visual de navegador, execução de 500 casos externos, teste de queda abrupta nem validação com dreams/learning/regulator ativos. Estes limites impedem chamar a revisão uma certificação de produção.

## 7. Código desnecessário ou complexidade a reduzir

Não recomendo apagar o grafo nem as fórmulas com base neste ensaio. Recomendo consolidar responsabilidades que hoje divergem:

- **Unificar listas de efeitos** em `toolsys`, `saydo` e benchmarks; atualmente nem concordam sobre `bash`. Os oráculos dos testes continuam independentes da decisão do runtime.
- **Retirar a escrita invisível da resposta HTML**; converter a intenção em uma ação explícita submetida à mesma autorização e recibo das ferramentas.
- **Eliminar auto-complete por “qualquer ferramenta funcionou”** e aceitação cega de `done`, depois de existir verificação por etapa.
- **Descontinuar implementação legada de chat**, conservando temporariamente a rota/CLI como adaptadores ao contrato único. Não quebrar consumidores silenciosamente.
- **Trocar migrações repetidas por versões idempotentes**; arquivar importadores pessoais/one-off sem os executar na base real. O modo dry-run não deve construir um motor que migra dados.
- **Reduzir estado `_turn_*` espalhado** com um objeto de contexto de execução; `turn_events` não deve ser também a autoridade de permissões só por ter sido extraído para reduzir linhas.
- **Consolidar clones e relatórios dos benchmarks**, não multiplicar scripts por cada frase que falhou. Conservar fixtures históricas e separar o código de avaliação da heurística avaliada.
- **Manter Fu/dream/learning como braços experimentais medidos**. Retirar do caminho obrigatório só o que perder uma comparação controlada de qualidade/custo; não declarar “código morto” apenas porque este conjunto não o ativa.

## 8. Pesquisa e consequência prática

O [LongMemEval](https://arxiv.org/abs/2410.10813) separa extração, raciocínio multi-sessão, temporalidade, atualizações e abstenção, com 500 perguntas. Serve para deixar de reduzir “memória” a acertar factos pessoais já conhecidos. A nossa próxima avaliação deve separar indexação, recuperação e leitura.

O [BFCL V3](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html) avalia estado de APIs e caminho de execução em interações com vários turnos. A aplicação aqui é verificar conteúdo dos ficheiros e efeitos por etapa, não confiar apenas no texto final.

O [AgentLTL](https://arxiv.org/abs/2607.02599) formula restrições sobre traces e verifica prefixos antes da execução. Inspira a localização da autoridade num ponto único anterior ao efeito. Não justifica chamar equivalentes os atuais filtros de frases/números.

O [MemSecBench](https://arxiv.org/abs/2607.27080) acompanha escrita, execução e esquecimento seletivo. É especialmente pertinente para verificar se retirar uma instrução realmente impede a sua reativação posterior, sem apagar conhecimento legítimo.

[Does Memory Need Graphs?](https://aclanthology.org/2026.acl-long.1232/) compara representações sob um enquadramento controlado e mostra a importância das escolhas de construção e recuperação. A recomendação para este projeto é uma inferência: testar a contribuição de Fu por ablação, preservar episódios originais e não confundir mais estrutura com melhor memória.

Nenhum destes estudos avalia diretamente HMG-Fu. Nenhum prova, por associação, que o projeto resolveu memória de AGI.

## 9. Prova de aplicação das 15 Golden Rules

| Regra | Aplicação nesta auditoria |
|---|---|
| 1. Fonte de verdade | HEAD, definições persistidas, documentação obrigatória, inventário/AST e SQLite só de leitura. |
| 2. Investigar antes de alterar | Diff de Claude, chamadores e reproduções antes de propor alterações; produção não alterada. |
| 3. Sem remendos de sintomas | Plano centra-se em afirmações, autorizações e recibos, não em mais frases hardcoded. |
| 4. Modularidade | Responsabilidades propostas sobre módulos existentes; contexto/evidência/execução com contratos explícitos. |
| 5. Não duplicar | Reutilização do fake engine dos testes e do motor real; consolidação de avaliadores/listas divergentes no plano. |
| 6. Planear primeiro | Fase 68 registada no ROADMAP antes dos diagnósticos; execução das melhorias permanece por autorizar. |
| 7. Atualizar o plano | Checkboxes da Fase 68 atualizadas com resultados à medida que as verificações terminam. |
| 8. Documentar | Este relatório, plano detalhado, três scripts e JSONs de prova; sem reparações escondidas. |
| 9. Full stack | Parser/ledger, grafo, ferramentas, planos, rotas, migrações, configuração, UI e benchmarks seguidos transversalmente. |
| 10. Sem funcionalidades ocultas | Nenhum flag de produção acrescentado; overrides e limitações dos diagnósticos declarados. |
| 11. Compatibilidade | Código/dados preservados; plano prevê adaptadores, migrações e rollback antes de remover caminhos antigos. |
| 12. Prova | 417 testes, 56 contratos, 20 turnos reais, comparação de retrieval e quatro contratos UI; riscos sem reprodução rebaixados. |
| 13. Camada correta | Distinção entre bug de escrita, bug de avaliação, falha do provider e limitação experimental. |
| 14. Ativos críticos | Base real só de leitura; dados sintéticos; shell/rede/skills externos bloqueados nas experiências. |
| 15. Interfaces claras | Estados blocked/failed/cancelled e eventos ignorados identificados; plano cobre restauro e visualização. |

As regras levaram a preservar o trabalho de Claude e a avaliar garantias observáveis antes de propor mais arquitetura. As limitações de cobertura manual, ferramentas de lint, ambiente e benchmark externo ficam explícitas: esta é uma auditoria reproduzível do estado observado, não uma garantia absoluta de correção.
