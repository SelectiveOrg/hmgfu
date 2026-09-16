# Plano executavel v2 — memoria que aprende e usa o que aprendeu

Autor: Codex, a pedido do utilizador. Executor: Claude. Data: 10/09/2026.
Estado: especificacao para implementar e validar um candidato; nada implementado por esta revisao.
Base observada: `7e470282423fd99d2e805dc253fc617318c7e04c` (91.AA).

Este documento e AUTONOMO e SUBSTITUI integralmente EXECUTION_PLAN_V1.md e o respectivo prompt. O v1 permanece como historico, nao como instrucoes concorrentes. Executar E0–E8 na ordem, incluindo validacao e entrega; nao parar apenas porque o codigo foi escrito. A execucao integral pode terminar em candidato rejeitado: nao autoriza esconder falhas nem garante atingir as metas.

## 0. Mandato, evidencia e limites

Ler `/golden-rules`, `/project-id`, PROJECT_ID.md, ROADMAP.md, docs/THEORY.md e actualizacoes V2/V3 nele referidas. Nao copiar pressupostos ou codigo para/de PA3. Revalidar o HEAD e configuracoes efectivos: o embedder actualizado no PROJECT_ID e bge-m3, apesar de instrucoes antigas mencionarem nomic. Conservar o modelo local 12B e os papeis actuais; nao trocar modelo para fazer passar testes.

Auditoria local: `reports/codex_last_five_20260910/ANALISE.md`, com scripts de leitura e sonda no mesmo directorio. Cinco sessoes, 23 trocas:

- O nome do cao foi corrigido no ledger e recuperado em duas sessoes novas: capacidade existente a preservar.
- Uma definicao ensinada foi conservada no episodio e encontrada por memory_search, mas nao usada em tres perguntas directas posteriores. Nao confundir ausencia de recuperacao com ausencia de armazenamento.
- A instrucao de pesquisar quando houver duvida ficou em output_prefix=none. A sonda reproduz a precedencia de um candidato errado sobre a deteccao de ferramenta e o prefixo acrescentado apos a resposta. A saida historica bruta do router nao foi capturada: nao apresentar a sonda injectada como replay do router real.
- Um resumo inventou uma expansao ausente do conteudo; outros derivados conservam versoes falsas. A contaminacao existe, mas a contribuicao causal de cada ponto para cada resposta ainda nao foi medida.

Esses exemplos sao DEV conhecido, nunca reservado. O relatorio contem contexto pessoal: NAO o copiar integralmente para documentos publicos ou push. Versionar somente uma sintese anonimizada, fixtures sinteticas e codigo. Este plano nao exige ler a base pessoal novamente.

### Objectivo do produto

`ensino -> proposta com origem -> esclarecimento se necessario -> feedback atribuido -> actualizacao persistida -> recuperacao com estatuto -> resposta/accao coerente -> reutilizacao limitada da interpretacao`.

Tres tipos de aprendizagem devem funcionar no MESMO protocolo:

1. Factos pessoais/relacionais: corrigir um nome sem alterar outra pessoa.
2. Definicoes de dominio: ensinar o significado de uma expressao num projecto e reutiliza-lo noutra sessao sem pistas.
3. Comportamento: ensinar, corrigir e revogar uma politica representavel; a confirmacao verbal deve corresponder ao estado executavel.

### Quatro alvos

Preservar originalidade >60%, eficiencia/utilidade 100%, prontidao de memoria para AGI 75%, como aspiracoes, nao escalas cientificas. ~37/~80/~50 sao estimativas historicas nao calibradas, NAO resultados actualizados. Acrescentar 100% de conformidade dos invariantes enumerados do protocolo, separado da taxa empirica de aprendizagem. Nenhuma contagem de testes ou melhoria de contrato demonstra originalidade Fu/AGI. Nesta execucao relatar resultados medidos, sem subir essas estimativas por intuicao.

### Autoridade e exclusoes

Autorizado ao executor: codigo/testes/docs do candidato hmg-fu, configuracao apenas nas bases sinteticas, commits e push de ficheiros publicos seleccionados para o remoto existente, checkpoints recuperaveis. Nao fazer force-push, publicar release, activar producao, reiniciar a aplicacao viva, alterar dados reais, hooks globais, credenciais ou PA3. Preservar alteracoes de terceiros, incluindo launch.json e serve_tailscale.py se ainda presentes; nao inclui-las automaticamente num commit.

Nao criar agente/nano/servico, scheduler/cron, motor de pesquisa, indice novo, treino de pesos, ontologia ilimitada ou campanha de limpeza. Nao resolver exemplos com listas de frases, nomes, siglas ou verbos. Nao iniciar novas fases fora deste documento.

Defeitos em dados reais, como a directiva antiga incorrecta, ficam para autorizacao separada de reparacao. Entregar plano de reparacao recuperavel, sem o executar. Correcao de codigo nao prova reparacao do estado vivo.

## 1. Arquitectura minima e atribuicao dos ganhos

### 1.1 Componentes

- **Uma percepcao:** ampliar opcionalmente a chamada de routing existente. A LLM propoe alvos/interpretacoes; nao autoriza SQL nem valida a si propria.
- **Um controlador:** contrato puro que decide perguntar, confirmar, rejeitar, corrigir, adiar ou invalidar, com evidencia e revisao esperada.
- **Tres adaptadores nos stores existentes:** factos em FactStore; definicoes em AssertionStore; comportamento em DirectiveStore. Uma decisao/recibo por efeito. Nao montar tres protocolos independentes.
- **Estado:** uma tabela learning_cases para pendencias, proveniencia e recibos, NAO outro ledger de verdade.
- **Exemplos:** MemoryPoint tipo pattern derivado de confirmacao humana, usando grafo/embedding existente; nao route_exemplars nem instrucoes executaveis.

No maximo dois modulos novos de produto: learning_protocol.py e learning_state.py; uma tabela nova learning_cases. Extensoes pequenas em stores/ingest/retrieve/router/cauda existentes. Nenhuma nova dependencia ou alteracao posicional de MemoryPoint.to_row/from_row. Evitar codigo ilegivel para cumprir limites; se uma fronteira fundamental nao couber, documentar alternativa minima antes de exceder o mandato.

### 1.2 Bracos sem confundir correccao com aprendizagem

| Braco | Conteudo | Uso |
| --- | --- | --- |
| B0 | Commit inicial congelado | Reproduzir e atribuir os defeitos conhecidos; nao e o controlo principal do protocolo |
| S | B0 + correccoes de integridade E2, protocolo off | Controlo principal; mede ganhos que nao dependem do protocolo novo |
| C | S + protocolo de ensino/feedback, sem exemplos na percepcao | Aprendizagem de factos, definicoes e politicas |
| L | C + acesso a exemplos confirmados | Teste de transferencia de interpretacao |

S/C/L partilham o MESMO commit de candidato, mudando apenas `interactive_learning_mode = off | confirm | adapt`, default off. S e re-medido nesse commit final; confirmar que o modo off coincide deterministicamente com o checkpoint de E2 nas entradas sem estado novo. B0/S e uma comparacao separada, nunca atribuida ao protocolo. Nao exigir igualdade com bugs de B0 que E2 corrige; enumerar previamente as mudancas autorizadas.

L requer learning_enabled ligado. Off impede nova aquisicao pelo protocolo, nao apaga nem revoga conhecimento valido ja guardado. A leitura das revisoes existentes continua pelos adaptadores documentados. Testes S iniciam sem casos/projeccoes de aprendizagem, nao reutilizam base treinada por C/L.

Uma nova configuracao publica em config/API/UI existente, sem painel novo. Limites centralizados/documentados: 4 propostas/turno, uma pergunta activa/sessao, duas tentativas/caso, dois exemplos/interpretacao, 100 exemplos activos/base. Novo esquema/interpretacao so em C/L. Nao criar tabela nova ao arrancar em off numa base legada; em C/L inicializacao lazily idempotente, inclusive quando o modo muda depois da construcao do engine.

## 2. Contratos de representacao

### 2.1 Envelope comum, estrito

Saida opcional memory_update, na chamada existente, com schema validado:

```text
feedback: none | confirm | reject | uncertain | correct | retract | approve_behavior | complain | resume_case
target_case_id: ID apresentado no snapshot ou null
scope: memory | behavior | plan | unclear
proposals: ate 4 {
  kind: personal_fact | domain_definition | behavior_policy,
  subject_ref, context_ref, relation, value, modality, valid_from,
  evidence_refs, replaces_assertion_id, operation
}
ambiguity: none | target | relation | value | time | contradictory | unsupported
```

Subschemas especificos por kind; additionalProperties=false; tipos/limites/IDs/operacoes verificados. Nao recuperar fragmentos de JSON para permitir escrita nova. Campos ausentes/invalidos nao significam confirmacao. Nao converter null em texto, confianca do modelo em prova, sujeito desconhecido em user, ou comportamento nao representavel em output_prefix.

IDs persistentes sao criados pelo controlador. Evidencia aponta para mensagem original+intervalos, alvo do snapshot ou pergunta realmente entregue. Verificar os intervalos e o contexto governante, nao apenas que o valor aparece algures numa citacao. Schema garante estrutura, NAO garante entendimento semantico: ambiguidades ou falta de suporte exigem esclarecimento e serao medidas em conversas reais.

Snapshot imutavel: sessao/turno estavel, projecto/contexto, ultima troca relevante, pergunta pendente exacta, plano pendente resumido, revisoes relevantes e 0–2 exemplos em L. Nao consultar objectos mutaveis do engine em workers. Truncamento e explicito e bloqueia escrita que dependa da parte omitida.

### 2.2 Factos pessoais

Manter catalogo/validacoes de slots, entidades, datas, negacao e terceiros. Entrada publica validada no FactStore; nao gerar uma frase artificial para reexecutar regex, nem usar trusted=True para contornar rejeicao. Facto claro pelo caminho actual nao ganha pergunta desnecessaria.

### 2.3 Definicoes fora dos slots pessoais — decisao ja autorizada neste plano

Usar entities/assertions existentes, com UM predicado generico de significado, por exemplo `definition.meaning`. A sigla/expressao e um VALOR de entidade contextualizada, nunca um novo slot. Termos novos cabem no mesmo contrato.

Identidade estavel da entidade = (contexto do projecto/escopo escolhido, termo). Implementar lookup idempotente com a infraestrutura de entities, sem colidir duas siglas iguais de projectos distintos. Reutilizar IDs existentes quando inequivocos. O controlador valida/cria a entidade, a LLM nao inventa IDs nem escolhe um projecto que nao foi apresentado. Se houver dois contextos plausiveis, perguntar; pasta seleccionada ajuda a escolher contexto, nao prova que seja o projecto principal da vida do utilizador.

Fixar em E1 uma chave deterministica dessa identidade usando ID estavel de projecto/escopo e normalizacao conservadora do termo. Manter termo original legivel; nao colapsar acentos/aliases sem evidencia. Sem projecto seleccionado, usar escopo local explicitamente identificado, nao global universal; nao propagar definicoes silenciosamente entre contextos. Se mudar o caminho de uma pasta, o contexto nao pode tornar-se outro apenas por um caminho novo: reutilizar a identidade de projecto existente quando disponivel.

AssertionStore.assert_ hoje supersede por entity_id+relation: por isso cada termo/contexto deve ser uma entidade propria. Nao usar a entidade user/projecto unica para TODAS as definicoes, o que apagaria a anterior. Nao mapear definicoes para identity.name ou open.<sigla>. Payload do caso conserva o contexto e ligacao da entidade; a verdade actual e a assertion, nao uma copia no caso.

Ensino literal claro de uma definicao contextualizada pode ser registado directamente com evidencia completa. Interpretacao inferida exige confirmacao. O sistema distingue 'o utilizador define X como Y neste projecto' de 'Y e uma verdade universal'. Em conflito com fonte externa, manter escopo e divergencia, nao reescrever conhecimento externo por autoridade pessoal.

Correccao/revogacao referencia a assertion/revisao exacta. Depois de reinicio ou sessao nova, resolver termo e contexto, consultar a revisao valida e injectar valor literal com origem/estatuto. Formula diferente/alias ambiguo depende de recuperacao/exemplo e pode pedir esclarecimento; nunca unir entidades so por proximidade vetorial.

### 2.4 Politicas de comportamento — nao sao formatos

DirectiveStore conserva a verdade das politicas, learning_cases conserva a prova/recibo. Usar kind tipado e payload validado para UMA politica inicial: `memory_lookup_on_insufficient_evidence`. Condicao `evidence_insufficient`, accao `memory_search`, fallback `ask_or_abstain`, escopo explicito. Reutilizar armazenamento de directives; o valor pode ser JSON versionado deste schema, nao texto a anexar a resposta. Variantes verbais sao interpretadas na chamada existente, nao regex de frases novas.

Separar claramente: formato literal, politica condicional de pesquisa e autorizacao de accao. A politica inicial autoriza apenas pesquisa interna de memoria da base corrente. Nao permite web, leitura de novos ficheiros, envio, execucao de plano ou ferramenta externa. Outros comportamentos continuam pelos contratos existentes; se nao representaveis, declarar o limite/perguntar, sem prometer adopcao.

Formato literal exige texto literal pedido como formato e ligacao de evidencia; 'none' explicitamente pedido como prefixo e legitimo. Proibir globalmente a palavra none seria remendo. Candidato sem valor/null ou incompativel com a instrucao nao pode criar formato; candidato errado nao deve silenciar uma interpretacao valida de ferramenta sem arbitragem verificavel.

Repreensao deve poder corrigir a directiva errada apresentada ao utilizador: ligar a reclamacao ao efeito e registo que o produziu, pedir confirmacao se houver varios alvos. Nao bloquear toda correcao por act=feedback. Revogar/substituir directiva e uma transicao auditavel; nao afectar regras independentes. Tombstones e migracoes nao podem ressuscitar a regra retirada.

### 2.5 Recuperacao orientada por evidencia, nao pela palavra 'duvida'

Nas perguntas substantivas em C/L, fazer uma consulta local limitada pelos canais existentes, mesmo se o router nao marcar needs_memory; reutilizar embedding/memo do turno. Saudacoes sem conteudo ficam fora, mas saudacao+pergunta nao pode ser silenciada como greeting. Esta verificacao nao e outra chamada de interpretacao nem um novo motor de pesquisa. Medir custo e capacidade de recuperar termos/definicoes sem injectar tudo.

Produzir EvidenceStatus com target/scope, IDs/revisoes de fontes, conflito, truncamento e estado: supported | missing | ambiguous | stale | unavailable. Para slots/definicoes, supported exige alvo/escopo/revisao correspondentes; semelhanca, memory_count>0 ou 'tenho certeza' nao bastam. Para respostas abertas, nao alegar uma prova semantica deterministica universal: declarar cobertura limitada e usar fontes verificaveis/perguntar quando necessario.

Politica activa + evidencia insuficiente para a resposta de memoria: executar memory_search real uma vez pelo caminho de ferramentas existente, com o pedido/escopo correcto. Se a mesma pesquisa ja correu no turno, reutilizar resultado/recibo em vez de duplicar. Incorporar resultado na resposta; se continuar vazia/conflituosa, perguntar pelo dado em falta ou abster-se. Nao insistir, pesquisar em loop, responder com uma expansao inventada ou repetir a certeza do router.

Memoria ja sustentada pode responder sem ferramenta adicional. Logo, 'nenhuma pesquisa' so e falha se o criterio rotulado exigia fallback; nao optimizar a metrica para pesquisar sempre. A politica e avaliada pelo estado de evidencia, nao interseccao de palavras como sure/answer entre regra e pergunta. Pedido misto preserva as partes independentes.

## 3. Proveniencia, resumos e memoria derivada

O conteudo fonte e imutavel como evidencia; resumos sao derivados, nao confirmacoes. Reutilizar source/status, assertions, justifications e macro_sources. Para material gerido pelo protocolo, ligar pontos/projeccoes ao case_id e IDs/revisoes de assertions nos campos existentes, sem novo indice nem segundo conjunto de factos.

Em E2, corrigir a fronteira comum de leitura de derivados: um resumo de assistant/dream nao pode ser fornecido como fonte autoritativa de um facto ensinado pelo utilizador. Para responder sobre factos/definicoes do utilizador/projecto, usar assertion valida ou trecho original de utilizador com estatuto; um macro pode indicar ONDE procurar, expandindo fontes existentes dentro do orcamento. Conteudo reflexivo sem prova continua reflexivo, nao se torna confirmado por titulo, repeticao, utilidade ou cabecalho.

Para novas proposicoes de C/L, renderizar a memoria factual curta deterministicamente da assertion/estado/evidencia; o resumo generativo permanece contexto opcional. Nao tentar provar entailment de qualquer resumo com uma regex ou um novo juiz LLM por turno. Para conteudo geral que nao caiba no contrato, conservar como episodio sem o promover e declarar o limite.

Ao corrigir/revogar, a revisao nova invalida a elegibilidade factual de derivados ligados a premissas antigas. Fazer esta verificacao na leitura, de modo que nao dependa de o sonho ja ter corrido; manter historico. Derivado com varias fontes nao leva a apagar factos independentes: reconstituir dos suportes validos ou nao usar o resumo como prova. Ligacao ausente/legada nunca equivale a confirmado; recuperar fonte ou apresentar como nao verificado.

Nao banir em bloco toda memoria de assistente: pode ser necessaria para recordar o que o sistema disse, propostas ou tarefas. Diferenciar 'o assistente afirmou X' de 'X e um facto do utilizador'. Preservar historia e perguntas sobre valores passados.

Testar antes/depois de consolidacao real numa base sintetica, com resumo que troca modalidade, inventa valor, repete versao antiga, mistura duas fontes e introduz instrucao. A existencia de source IDs nao prova que um resumo lhes seja fiel. Relatar escrita de resumo indevido e exposicao factual indevida separadamente; esta fase exige impedir a segunda, nao promete que o nano jamais gere texto errado.

## 4. Protocolo de conversa e persistencia

### 4.1 Estados e dono do feedback

learning_cases: id, session_id, state, revision, created_at, updated_at, origin_turn_id, question_turn_id, payload_json. Payload estrito com propostas, evidencias, revisoes esperadas, pergunta entregue, feedback literal, recibos/IDs e projeccoes pendentes. Indice/garantia transaccional de no maximo uma pergunta activa por sessao.

Estados `proposed -> awaiting -> committed | rejected | deferred | invalidated`. Uma escrita literal segura pode ir a committed; inferencia nova precisa de confirmacao. No-op e `reiteration`, nao nova aprendizagem. IDs de eventos criados antes da resposta e independentes de turn_seq reutilizado apos crash.

| Entrada/condicao | Efeito |
| --- | --- |
| Facto/definicao/regra explicita suportada | Validar e guardar no store certo; nao perguntar por rotina |
| Falta alvo/valor/contexto ou ha conflito | Uma pergunta focada; nao escrever a interpretacao pendente |
| Sim a pergunta unica realmente entregue | Confirmar so a proposicao apresentada e revisao ainda actual |
| Nao a proposta ainda nao gravada | Rejeitar; preservar estado anterior, sem inventar alternativa |
| Nao a verificacao da validade de facto existente | Retratar apenas o alvo/revisao que a pergunta identificou |
| Nao, e Y com alvo unico | Corrigir esse alvo; se Y/escopo ambiguo, esclarecer |
| Talvez / nao sei / ausencia | Adiar; nao promover nem insistir automaticamente |
| Elogio generico | Nao confirmar todos os factos/exemplos; nenhum treino factual automatico |
| Repreensao | Identificar alvo/efeito; corrigir se inequivoco, senao perguntar; nao penalizar toda a memoria |
| Feedback de ferramenta/estilo | Usar adaptador de comportamento, nunca slot de identidade |
| Plano e memoria pendentes | Resolver dono do feedback; um sim nao pode aprovar ambos |
| Mudanca de assunto | Adiar; sim tardio solto nao reabre o caso |
| Nova sessao | Conhecimento valido disponivel; pendencia de outra sessao nao consome resposta |
| Reinicio na mesma sessao | Retomar apenas pergunta ainda pertinente e revisao actual |
| Actualizacao concorrente / caso revogado | Falhar compare-and-swap, nao sobrescrever ou ressuscitar |
| Payload invalido/indisponivel | protocol_unavailable; nao confirmar memoria/plano por defeito |

Maximo uma pergunta por resposta, duas tentativas por caso. Esclarecer quando a incerteza e relevante para o pedido, nao toda mencao. Depois do limite, explicar lacuna e permitir outro assunto. Guardar candidato sem pergunta entregue nao autoriza consumir sim. Persistir a pergunta visivel exacta; evitar segunda chamada apenas para formular esclarecimento.

### 4.2 Uma transaccao por actualizacao logica

decide_learning(snapshot, observation, proposals) e puro: retorna pass_through/ask/commit/reject/defer/invalidate, owner, handled_targets, blocked_proposals, independent_writes, question, reason. Sem SQLite, modelo ou ferramentas dentro da decisao.

Adaptadores publicos usam conexao/transaccao partilhada, locks e validacoes. AssertionStore ja aceita conn sem commit proprio; estender DirectiveStore com o mesmo principio preservando API legada. learning_state participa da conexao do commit, nao faz commit autonomo a meio. Correcao que remove um formato errado e cria politica certa e atomica com o estado do caso. Nao manter locks de stores diferentes em ordem inversa: documentar uma ordem unica e testar concorrencia.

O caso committed, revisao do store e recibo sao atomicos. Projeccao no grafo ocorre depois, e idempotente/retomavel. Leitura do dado confirmado nao pode depender de a projeccao acabar: consultar store ou indicar pendente; nao dar recibo de plena disponibilidade falso. Testar crash em cada fronteira, retry, revisao obsoleta e duas sessoes alternadas.

Para sim, guardar pergunta/proposta E resposta confirmatoria. Nao fabricar citacao 'o meu nome e Y' como se estivesse no sim. Evidencia do turno original/pedido e ligada posteriormente ao transcript persistido por ID estavel, nao 'ultima mensagem'. link_source/link_episode nao podem reassociar outra entidade/revisao. Restricoes exactas por alvo, nunca retract/supersede amplo por coincidencia de valor.

### 4.3 Integracao de ponta a ponta

- agent.py: snapshot antes de consumir aprovacao; decisao/commit antes de montar contexto da resposta; transportar decisao imutavel.
- session_plans.begin_turn hoje precede router: em C/L separar leitura de plano de consumo de aprovacao; memoria nao aprova ferramenta. Off preserva comportamento de S.
- turn_router/sensitizer/extraction_schema/QueryPoint/make_query_point: transportar schema opcional sem perda, substituicao pelo nano ou defaults permissivos.
- FactStore/AssertionStore/DirectiveStore: planeamento e aplicacao separados, sem executar mapper duas vezes.
- turn_tail/TailContext/grader/correction_queue: transportar sessao, turno, alvo/revisao, suspensos/tratados. Nao reescrever alvos ja decididos; nao desligar correccoes independentes da mensagem mista. Revalidar ao drenar trabalho tardio.
- ingest/retrieve/organise_for_injection/build_llm_context e tool memory_search: a mesma politica de proveniencia/estatuto em todas as saidas. Corrigir so um caminho e deixar o outro injectar resumo falso nao conclui a etapa.
- sessions/turn_events/API/WS/settings UI: mostrar modo e recibo reais nas superficies existentes, restaurar apos reload, invalidar pendencias ao excluir sessao. Sem painel novo.

Uma resposta exclusivamente de esclarecimento nao pode ser substituida pelo relogio. Pergunta mista legitima sobre horas continua a funcionar. Nao transformar modo learning num bypass de grounding, autorizacao ou contratos de 91.AA.

### 4.4 Recibo honesto

Separar `received`, `pending_clarification`, `committed`, `reiteration`, `rejected`, `unavailable`. committed inclui tipo, ID/revisao, origem, efeito e disponibilidade. 'Recebi' nao equivale a 'aprendi'; 'active policy' exige tipo valido e executor ligado; 'pesquisei' exige resultado/recibo da ferramenta. Nao fabricar tool receipts para escrita interna. Nao prometer 'nunca esquecerei'.

## 5. Aprendizagem da interpretacao — L versus C

Depois de confirmacao/correcao humana com commit, gerar um exemplo estruturado sem chamada extra: expressao/contexto, interpretacao, correcao, escopo, evidencia e case_id. Guardar pattern com marcador learning:interpretation. Reutilizar embedding existente se valido para esse conteudo; nao rotular um vector de outro texto como se tivesse sido calculado para o exemplo. Chamadas necessarias contam no custo.

Maximo dois exemplos na percepcao, filtrados por base, contexto, revisao valida e revogacao. Nao usar limiar kNN de ferramentas sem validacao. Em conflito, abster-se/perguntar. Exemplos nunca autorizam accoes, copiam valores antigos para novos sujeitos ou entram como factos canonicos. Texto com instrucoes maliciosas e dado, nao comando. Elogio, resposta do proprio modelo, sonho ou sucesso de ferramenta nao confirma exemplo.

Ao limite de 100 activos, tornar antigos inelegiveis por politica documentada, sem apagar prova. Revogar um caso invalida o exemplo imediatamente. C/L mantem os mesmos factos/episodios de ensino; varia somente acesso aos exemplos. Recuperar o mesmo significado de sigla demonstra retencao, NAO transferencia: esta exige nova formulacao/contexto compativel, outro valor e negativo proximo respeitado.

## 6. Instrumentos e conjuntos, antes de implementar

Reutilizar runner/juiz/say-do existentes. Nao usar a funcao do produto que classifica modalidade/learning para dar a si propria o veredicto. Rotulos independentes de estado, texto e ferramentas. Juiz com positivos e negativos: valor negado/citado/passado, sujeito errado, resposta que nao expande sigla, promessa sem escrita, pesquisa sem uso, pergunta que sugere valor errado, inconclusivo. Zero erro nos negativos de seguranca antes de aceitar o instrumento.

Runner: bases sinteticas novas com caminhos explicitos e destinos unicos; recusar colisao/producao. clone_live pode escolher DB real por defeito e apagar destino: nao usar defaults. fresh_engine pode desligar grader apos settings: verificar configuracao EFECTIVA e execucao dos hooks. Guardar respostas/perguntas/feedback completos; se truncados, nao dar PASS sem evidencia. Logs com dados reais nao entram no Git.

### 6.1 Testes deterministas P

Enumerar todas as transicoes da tabela e invariantes: payload invalido/null, IDs inventados, evidencias falsas, multi-proposta parcialmente confirmada, pergunta nao entregue, sim de outra sessao, plano+memoria, retry/crash, revisao concorrente, revogacao, duas bases, TTL logico por mudanca de assunto, mapper/spans/grader e cauda sync/async. Acrescentar:

- Duas definicoes no mesmo projecto nao se supersedem; mesmo termo em dois projectos nao se confunde; reinicio preserva resolucao e isolamento.
- Formato literal legitimo incluindo none preservado; null/ausencia ou politica mal tipada nunca anexados como formato; reclamacao pode revogar a regra errada sem apagar outra.
- Politica dispara por falta/conflito de evidencia, nao palavras da regra; resposta ja sustentada evita pesquisa duplicada; falha da ferramenta nao gera certeza nem accao externa.
- Resumo inventado nao vira prova, correcao invalida dependencias antigas, macro com varias fontes preserva as independentes, ausencia de ligacao nao confirma legado.
- Ponto/recibo repetido nao soma aprendizagem; desligar modo nao apaga conhecimento; off com base legada nao cria estado de protocolo.

P = invariantes/transicoes enumerados cumpridos / total enumerado, alvo 100%. Stubs provam controlo, nao entendimento da linguagem.

### 6.2 Conversas naturais

Manter o tamanho do v1: **24 DEV + 48 reservadas**, reformulando as 12 familias para incluir as falhas reais sem multiplicar campanhas. Cada familia: 2 DEV (PT/EN), 4 reservadas (2 PT/2 EN). Cada episodio 4–8 mensagens do utilizador, com politica de feedback fixada. Transicoes adicionais ficam na suite determinista, nao se afirma cobertura linguistica exaustiva.

| Familia | Criterio primario |
| --- | --- |
| F01 | Ambiguidade -> pergunta -> sim vinculado; novo turno e nova sessao |
| F02 | Nao/correccao por referencia; rejeitar versus retratar, alvo unico/multiplo |
| F03 | Talvez, silencio, mudanca de assunto e sim tardio; nao aprender falsamente |
| F04 | Sujeitos/mensagens mistas/datas; preservar factos nao corrigidos |
| F05 | Plano versus memoria, reinicio e sessao; nenhuma autorizacao cruzada |
| F06 | Definicao nova de dominio, consulta noutra sessao sem pista, termo nao predefinido |
| F07 | Corrigir/revogar definicao; termo igual em dois projectos; definicoes independentes |
| F08 | Ensinar politica de pesquisa por evidencia insuficiente; execucao e resposta sustentada |
| F09 | Repreender/corrigir/revogar politica errada; elogio generico nao aprova factos |
| F10 | Correcao versus resumo/macro falso; apos consolidacao nao reincidir |
| F11 | Transferencia de interpretacao; novo valor/formulacao e negativo proximo |
| F12 | Controlos claros, formato legitimo, perguntas gerais/horas; nao perguntar/pesquisar sempre |

Em cada familia metade arranca vazia, metade com fixture de 20 distractores sinteticos e historico antigo plausivel. Nos F07/F10 incluir derivados errados com fonte identificada, em E1 antes de ver saidas. Projecto seleccionado/nao seleccionado e escopos PT/EN declarados. Nunca usar historia pessoal viva como distractor. Nomes/valores ineditos no reservado; controlar semelhanca por familia e estrutura, nao so igualdade literal.

Manifesto por episodio: requires_learning, requires_clarification, tipo/escopo/alvo, evidencias, mudancas permitidas/proibidas, estado antes/depois da cauda, resposta admissivel, ferramentas permitidas, condicao de pesquisa e politica de feedback. Definicao exige significado correcto, nao uma descricao vaga da funcao. Regra exige estado executavel E comportamento num pedido novo que active a condicao.

Sim so e enviado se a pergunta visivel corresponder ao alvo/proposicao rotulados; caso contrario rejeicao/esclarecimento fixados. Nao usar LLM como utilizador que ajuda silenciosamente o candidato. S e L recebem a mesma politica, embora produzam perguntas distintas; contar todas as mensagens/custos. Falta de pergunta obrigatoria e falha, nao atalhar para resposta ensinada.

Selar reservado/rotulos/hashes antes de produto, sem gerar respostas. Executor que autorou conhece o conjunto: chamar reservado, nao duplamente cego. Saidas nao podem ser usadas para afinar. Depois de aberto, vira DEV para qualquer revisao que use esse feedback.

### 6.3 Transferencia e preservacao apos sonho

Selar **12 episodios reservados de transferencia**, 6 PT/6 EN, cada um positivo+negativo proximo. C/L com factos/episodios de ensino iguais e acesso a exemplos como unica diferenca; 2 repeticoes/braco. Confirmar igualdade de estados antes da consulta; diferencas posteriores sao resultados, nao alterar dados para forcar igualdade.

Procedimento da ablacao: para cada episodio, realizar a fase comum de ensino/confirmacao pelo protocolo C, gerar os exemplos derivados dos recibos (armazenados em ambos os modos, usados apenas em L), congelar esse estado sintetico e criar duas copias identicas para as consultas C/L. Repetir desde estado inicial novo na segunda repeticao. Nao preencher assertions manualmente para salvar um ensino que falhou: a falha de preparacao conta no denominador e e declarada. O custo da preparacao comum conta no total; relatar separadamente custo de ensino e de consulta. A comparacao principal S/L continua a medir a aprendizagem completa sem esse estado partilhado.

Teste pos-consolidacao integrado em F10: semear fontes/derivados controlados, executar o sonho existente de forma explicita, mesma configuracao/agendamento em S/L, registar chamadas/custo e comparar antes/depois. Sonho automatico desligado igualmente para isolamento; este teste usa o pipeline real, nao so resumo injectado. Nao desenvolver 'sonho novo'.

## 7. Metricas e portas fixadas

### Metricas

- P: conformidade determinista enumerada.
- A: aprendizagem ponta a ponta, causada pelo ensino/feedback do proprio episodio, estado correcto e consulta nova correcta; exige sucesso nas duas repeticoes. Denominador todos requires_learning, incluindo timeout/inconclusivo como insucesso, relatados separadamente. Separar pessoal, definicoes e comportamento.
- C: episodios com todas as transicoes/restricoes satisfeitas / todos.
- R: reincidencias em consulta pos-correcao / consultas previstas; incluir derivados antigos afirmados como actuais.
- W: escritas indevidas novas por caminho, antes e depois da cauda/drenagem.
- Q: esclarecimentos obrigatorios correctos / obrigatorios; desnecessarios / turnos claros.
- D: definicoes recuperadas e respondidas correctamente sem pista / consultas elegiveis.
- B: politica correctamente persistida E aplicada/revogada / episodios comportamentais; contar chamadas indevidas separadamente.
- G: derivados sem suporte apresentados como facto confirmado / consultas de proveniencia; contar geracao de resumo defeituoso separadamente.
- H: afirmacoes de actualizacao/pesquisa sem recibo correspondente / afirmacoes dessa natureza.
- T: transferencia C/L pareada, incluindo negativos proximos.
- Custo: chamadas por papel, tokens quando disponiveis, p50/p95 resposta e memoria utilizavel, por turno e episodio; total inclui retries/descartes/sonho. Medidas da auditoria real (mediana 8,6 s, 11,2 chamadas agregadas) nao sao baseline pareado nem limite universal.

### Portas para reservado

P=100%; suite integral sem novas falhas/xfail/skip; contraste32 e multi-facto28 preservados; truth core e write sets v1–v5 sem novas perdas/escritas indevidas face ao baseline apropriado e mesmo oraculo. Saidas mudadas por E2 precisam de atribuicao e criterio aprovado, nao editar gold para salvar candidato.

DEV C/L sem nova escrita indevida, sem autorizacao cruzada, sem recibo falso e com positivos reconhecidos nas tres classes (protecao nao vacua). Demonstrar em DEV o ciclo de definicao, politica e consolidacao antes do reservado. Codigo/runner/config/conjuntos congelados e custo previsto dentro do orcamento.

### Reservado principal

S versus L: 48 episodios x **2 repeticoes por braco**, AB/BA alternado predefinido, bases novas por episodio/repeticao. Mesmos modelos/contextos/settings salvo modo. Repeticoes do mesmo episodio nao sao observacoes independentes: IC95% por bootstrap pareado de 10 000 amostras por episodio, agrupando repeticoes.

Para recomendar adocao do candidato, sem activar producao:

1. P=100%; zero W novo atribuivel ao candidato, zero fuga de escopo/base/sessao, zero autorizacao indevida, zero H; G=0 nos casos previstos. Erros de resposta factual do novo protocolo nao podem ser escondidos por ledger correcto.
2. A>=80% estavel 2/2 e ganho >=10 pontos percentuais sobre S. Publicar tambem B0->S separadamente, sem soma causal artificial.
3. Definicoes e comportamento: >=75% dos episodios elegiveis de CADA classe com sucesso estavel, nenhuma classe abaixo de S. Estes pisos sao obrigatorios para evitar passar apenas pelos nomes pessoais; denominadores fixados em E1, nao depois.
4. Nenhum caso S 2/2 correcto se torna L 0/2. Flips 1/2 sao instabilidade declarada. R<=5%; Q obrigatorias>=90%, Q desnecessarias<=5%. Aplicar limites a contagens inteiras sem arredondar para cima a conveniencia.
5. Turnos claros sem necessidade de pesquisa/esclarecimento: zero chamadas novas de LLM por turno, p50<=1,20x S e p95<=1,30x S. Episodio completo: chamadas medias<=1,25x S; pesquisas necessarias/embedding/sonho sao contados. Amostra pequena nao prova equivalencia de latencia.

T exige pelo menos 3 episodios estavelmente ganhos de L sobre C, zero estavelmente perdidos e zero promocao indevida de negativo proximo. Se T falhar, nao recomendar modo adapt; C so pode ser recomendado depois de validacao reservada equivalente propria, NAO inferindo que passou porque L foi medido. Neste orcamento e valido entregar C promissor mas nao validado, sem campanha adicional automatica.

IC do ganho incluindo zero -> promissor/inconclusivo quanto a superioridade, mesmo se cumprir limites de engenharia. Qualquer porta obrigatoria falhada -> nao adoptar agora. Nao alterar alvo/regra apos medir. Testes finitos nunca garantem ausencia universal de regressao.

## 8. Execucao E0–E8

### E0 — Fonte, seguranca e plano versionado

- [ ] Ler fontes e revalidar HEAD/diff/processos/settings; preservar trabalho alheio e produto vivo.
- [ ] Copiar esta v2 para docs/INTERACTIVE_LEARNING_EXECUTION_V2.md, publicar apenas a sintese anonimizada dos achados e actualizar quarto objectivo no PROJECT_ID. Registar E0–E8 no ROADMAP antes de produto.
- [ ] Checkpoint recuperavel de B0, commit/tag/ramo e push de publicos seleccionados; verificar referencia remota. Se working tree tiver ficheiros privados/alheios, isolar candidato sem os incluir/reverter.
- [ ] Criar workspace/candidato e bases sinteticas independentes; manifesto inicial de modelos, env efectiva, versoes e permissoes.

Saida: baseline fixado, rollback, plano assumido. Nao pedir nova aprovacao de cada passo ja contido neste mandato.

### E1 — Instrumentos e reproducoes

- [ ] Selar DEV24/reservado48/transferencia12, rotulos, condicoes de feedback, interferencia e custo por etapa previsto. Acrescentar testes deterministas enumerados.
- [ ] Adaptar runner, perfil efectivo, juiz independente e telemetria; provar negativos do juiz. Capturar pergunta, feedback, origem, raw router quando disponivel, estado antes/depois, fontes realmente injectadas, resposta bruta/final e recibos.
- [ ] Reproduzir defeitos conocidos em fixtures sinteticas: directiva mal tipada, resumo sem suporte e definicao nao reutilizada. Executar uma pequena leitura com router real, alem de stubs; se nao reproduzir a classificacao, dizer isso e manter a prova do mecanismo separada.
- [ ] Demonstrar capacidade actual de correcao pessoal e ausencia de escrita/cruzamento indevido; nao tentar corrigir B0.

Saida: instrumentos que distinguem guardar, recuperar, usar e cumprir uma politica.

### E2 — Integridade primeiro, baseline S

- [ ] Corrigir validacao/arbitragem de directivas na camada existente: tipos, valores, evidencia, preservar formatos legitimos e ferramentas. Teste primeiro a falhar, depois passar.
- [ ] Fechar fronteira de proveniencia de resumos/derivados na leitura/contexto e memory_search; fontes originais e estatuto preservados, sem apagar memorias do assistente em bloco.
- [ ] Testar reclamacao/retirada no mecanismo existente; o protocolo de feedback mais geral vem em E3/E4. Nao afirmar que corrigir parser implementou toda a aprendizagem.
- [ ] A/B B0/S nos casos dirigidos com positivos e negativos, suite/regressoes afectadas. Congelar checkpoint S; medir S no DEV24 uma vez.

Saida: bugs de integridade corrigidos e ganhos atribuiveis separados. Nenhuma reparacao da base viva.

### E3 — Estado e tres adaptadores sem modelo

- [ ] Implementar controlador/tabela/transicoes e tres adaptadores validados, reusando assertions/directives/facts; testes antes das mudancas.
- [ ] Resolver entidade termo+contexto e politica tipada, sem novo slot por valor. Conexao partilhada, revisao esperada, idempotencia, recibo e projecao recuperavel.
- [ ] Testar pergunta entregue, dono do sim, plano concorrente, revogacao, reinicio, duas sessoes/bases e crashes; P=100% antes do vivo.

Saida: protocolo mecanico correcto, nao alegar percepcao linguistica comprovada.

### E4 — Ligar C ao turno, pesquisa e resposta

- [ ] Integrar schema e contexto na chamada existente, arbitragem pre-resposta, stores, cauda e correccoes tardias; matriz sync/async e mapper/spans.
- [ ] Ligar EvidenceStatus, consulta local e politica memory_search condicional; sem duplicacao de pesquisa, sem nova chamada para 'autoavaliar confianca'.
- [ ] Ligar recibo honesto, pergunta visivel, API/WS/UI settings e persistencia apos reload; confirmar limites de escopo do projecto.
- [ ] Piloto vivo de seis DEV predefinidos F01/F05/F06/F08/F10/F12, PT/EN; corrigir por hipotese na camada certa.
- [ ] Correr C no DEV24; trace mostra o ciclo completo nas tres classes e apos consolidacao.

Saida: ensino->feedback->estado->recuperacao->resposta/accao comprovado em DEV.

### E5 — Ligar L e medir transferencia DEV

- [ ] Criar exemplos confirmados, filtros de validade/escopo/revogacao e limite de dois; nunca transformar exemplos em instrucoes ou novo indice.
- [ ] C/L em seis casos DEV adicionais de transferencia rotulados em E1; nao usar os 12 reservados.
- [ ] Correr L DEV24; verificar portas pre-reservado e ausencia de proteccao vacua. Congelar candidato.

Saida: aprendizagem de interpretacao separada da retencao de valores.

### E6 — Compatibilidade, custo e congelamento

- [ ] Suite integral e regressoes, S/C/L e combinacoes importantes de cauda/mapper, invariantes de 91.AA; listar todas as diferencas autorizadas de E2.
- [ ] Calcular custo total restante com piloto vazio/interferencia/consolidacao, repeticoes, ablacao e margem de 25%. Afirmar env efectiva depois de fresh_engine, nao apenas argumentos CLI.
- [ ] Selar commit, runners, manifests e hashes; guardar cenarios/publicos e backup remoto. Nao editar codigo/script/config enquanto uma cadeia corre.

Saida: autorizado tecnicamente a abrir reservado somente se todas as portas e orcamento couberem.

### E7 — Reservado, sem afinacao

- [ ] Executar S/L 48x2 por braco e C/L transferencia12x2 por braco, uma cadeia de GPU por vez, bases novas e ordem fixada.
- [ ] Verificar traces/cauda/proveniencia, calcular metricas por familia/tipo, estabilidade e IC pareado. Contar timeouts, falhas e custos de descartes.
- [ ] Aplicar portas originais. Se falhar, entregar resultado negativo; nao reparar candidato contra este reservado nem abrir outro automaticamente.

Saida: validacao completa e decisao sustentada, positiva ou negativa.

### E8 — Entrega integral

- [ ] Demonstracao sintetica curta com factos, definicao nova, politica, correcao/nao/talvez, sessao nova e consolidacao; usar dados DEV, nao chamar demonstracao de benchmark.
- [ ] Relatorio: implementado/ligado/activado separados, B0/S/C/L, portas e numeros completos, perdas/limites/erros, custo e complexidade. Quarto eixo desagregado; nenhuma percentagem teorica inventada.
- [ ] Plano de rollout/rollback e eventual reparacao de dados reais em dry-run documentado, SEM executar na base pessoal. Avisar que a aplicacao viva pode continuar com codigo/dados anteriores.
- [ ] Actualizar ROADMAP/PROJECT_ID com evidencia; commit/push apenas publicos, verificar remoto e estado dos processos proprios. Nao encerrar processos da aplicacao ou de terceiros.
- [ ] Entregar conclusao: candidato apto para decisao de activacao OU nao adoptar/inconclusivo com bloqueio exacto. Nao iniciar fase seguinte.

## 9. Orcamento, autonomia e paragens

Esta v2 propoe **6 horas cumulativas de GPU**, em vez das 4 horas do v1, devido a integridade/proveniencia, baseline S e consolidacao real acrescentados. Nao e estimativa nem promessa de duracao; a autorizacao deste limite vem do prompt que o utilizador enviar. Inclui warm-up, retries, testes de modelo, descartes, consolidacao e reservado; CPU/desenvolvimento reportados separadamente. O piloto de E6 deve caber no saldo com margem; nao iniciar uma corrida que previsivelmente o exceda.

No maximo duas iteracoes de hipotese por E2, E4 e E5; muda de prompt/contrato conta. Regressao introduzida exige primeiro reproduzir e tentar correcao dentro dessa etapa; se nao resolver no limite, isolar/reverter apenas alteracao propria com checkpoint e entregar bloqueio. Nao chamar cada frase/commit uma hipotese nova. Defeitos preexistentes sem relacao com este ciclo ficam nomeados, nao abrem campanhas.

Uma cadeia GPU por vez, sem cron novo. Reutilizar monitor, informar apenas mudanca material e entrega; nao fazer polling caro/repetitivo. Timeout conta; uma reposicao por etapa apenas por causa ambiental identificada, com par completo e custo preservado dentro do saldo. Se codigo mudar, invalidar corrida e contar custo, nao esconder.

Continuar pelas etapas autorizadas sem pedir aprovacao em cada checkpoint. Parar so por falta de autoridade, risco a activos, fronteira arquitectural material, orcamento insuficiente, ambiente nao recuperavel ou falha de porta que proibe a etapa seguinte. Nao rebaixar uma porta para conseguir dizer 'executado na totalidade'. Se bloqueado, E8 continua possivel como relatorio de entrega parcial: enumerar etapas nao executadas e comando/decisao necessarios para retomar, sem afirmar objectivo atingido.

Ausencia de novo memory_update por bypass deve ser protocol_unavailable, nunca confirmacao inventada. No perfil principal fixar kNN/router_bypass OFF como base; testar compatibilidade separada sem alterar perfis a meio. Nao esconder chamadas de reparacao/juiz na cauda. Nenhuma mudanca de hardware/modelo por conveniencia.

## 10. Prova final e limites do desenho

Relatorio deve conter: versoes/hashes/configs; tabela E0–E8; resultados B0->S separados de S->L e C->L; P/A/C/R/W/Q/D/B/G/H/T com numeradores/denominadores; latencia/chamadas/custo total; todas as perdas novas/preexistentes/inconclusivas; migracoes e rollback; aderencia individual as 15 golden-rules e violacoes.

Este plano usa inspecao focada e a auditoria de cinco conversas, nao uma prova exaustiva do produto. Mapeamento semantico e previsao de incerteza continuam faliveis no 12B; contratos restringem efeitos e medem a capacidade, nao tornam a LLM infalivel. O alvo de 100% aplica-se aos invariantes enumerados, nao a todas as linguas e formas futuras. Nao afirmar 'sem regressao' fora do escopo realmente testado.
