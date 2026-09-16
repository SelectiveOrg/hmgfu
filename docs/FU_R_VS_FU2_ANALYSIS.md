# Fu-R (Codex) × Fu 2 (Claude) — análise comparativa e decisão de integração (2026-09-05)

Fontes: `reports/fu_theory_proposal_20260905/FU_R_PROPOSTA.md` (Codex), `docs/FU_THEORY_ASSESSMENT.md` §4 (Fu 2).
Verificado antes de opinar: o `check_concepts.py` do Codex passa (16/16 verificações conceptuais, incluindo AND/OR,
revisão em DAGs aleatórios e o contra-exemplo ao "MRR desce necessariamente"); e a divergência que ele aponta entre
THEORY v2 (ranking por cosseno, A.1 falsificado) e `retrieve.py` é real mas incompleta — o código tem os DOIS caminhos
(`memory_score` + `expand_through_fu` na linha 145–153 e cosseno puro na 164), seleccionados pelos pesos configurados
(`--weights fu|lean` nos benches); o que corre em produção depende da definição persistida, e isso deve ser registado
em cada experiência, como ele pede.

## 1. Onde as duas propostas concordam (e por isso são provavelmente certas)

| Ponto | Fu-R | Fu 2 |
|---|---|---|
| A unidade não é o ponto | intervalo = dependência/condição verificável | intervalo = afirmação evidenciada |
| Afirmação tipada | C = (entidade, relação, valor, polaridade, modalidade, âmbito, tempo válido, tempo de registo, fontes) | (sujeito, relação, valor, polaridade, modalidade, validade temporal, trecho, episódio) |
| Modalidade | afirmação / citação / hipótese / intenção | idem (a Fase 69 já veta citação e hipótese lexicalmente) |
| Entidades | dois cães = duas entidades | idem (M3) |
| Verdade ≠ autorização | permissão de acção nunca herdada do texto | invariante 2 (registo de autorização + recibo) |
| Recibos | conclusão de trabalho exige recibos (M2) | invariante 2 |
| Macros/sonhos | caches com fontes e versões, invalidáveis; nada se confirma por ter sido sonhado | consolidação só com derivação explícita |
| Hexágonos/wormholes | visualização / hipótese fora do núcleo | braço experimental por ablação |
| Fórmula F original | preservar como histórica, não decide memória | manter como peso, redefinir N como evidência |
| Método | braços controlados, falsificadores pré-registados, custo total contado | idem (MemDelta) |

## 2. Onde diferem, e qual é melhor

**O intervalo.** Fu-R faz do intervalo uma JUSTIFICAÇÃO: (premissas, conclusão, tipo, condições, estado de revisão),
com AND/OR à TMS/proveniência. Fu 2 fazia do intervalo uma afirmação com peso de evidência. A de Codex é mais rica e
mais honesta: separa "isto sustenta aquilo" de "isto é verdade", permite justificações alternativas (retirar A não
mata D se E também o sustenta) e dá um algoritmo de revisão localizado. A minha aresta-afirmação é um caso particular
(justificação com uma premissa: o episódio). **Adoptar a de Codex como representação de M3**, com o meu peso de
evidência em log-odds como o proxy barato de "força de suporte" (número de fontes independentes), explicitamente
separado de utilidade.

**Utilidade.** Fu-R define ganho `G(f|Q,K) = U(K com f) − U(K sem f)` e a interacção `I_Fu` (diferença de diferenças),
medidos externamente e offline, para decidir cache/prioridade — não verdade. Correcto e caro: é combinatório e ruidoso
com modelos locais pequenos. Fu 2 propunha usar o sinal do grader ("recordar isto mudou o resultado") como utilidade
por item. **Adoptar a definição de Codex como definição** e o sinal do grader como o estimador de baixo custo, com
"utilidade desconhecida" quando não há rótulo — como ele exige.

**Novidade.** Codex é mais rigoroso: classifica Fu-R como síntese de investigação (TMS 1979, ATMS 1986, semianéis de
proveniência 2007, Zep, HippoRAG 2, Invalidation Contracts 2026) e isola o único diferencial defensável, H-Fu: a
política ADAPTATIVA que escolhe que pacotes relacionais pré-calcular, manter ou reconstruir pelo ganho medido ao longo
de consultas E alterações. Concordo, e é isto que baixa a minha própria estimativa de originalidade "atingível": sem H-Fu
provada contra o controlo B2 (TMS/cache com política fixa), o que temos é engenharia boa de proveniência, não teoria nova.

**Correcção que ele acerta e eu não tinha:** "validade depende da pergunta" (§2.4). O nosso `supersede_stale_nodes`
demove evidência histórica globalmente; uma pergunta histórica ("onde vivia eu em 2025?") pode perder a resposta.
Entra em M3 como requisito: validade avaliada no tempo da pergunta, não por demoção global.

**O que falta a Fu-R (e Fu 2 cobre):** eficiência/latência (o nosso pior número), memória procedimental (runbooks),
prospectiva, abstenção calibrada, escala. Fu-R é uma teoria da verdade e da revisão; não é um programa de sistema.

## 3. Riscos de Fu-R que quero deixar escritos antes de implementar

1. A extracção de dependências a partir de conversa natural é o passo difícil; o próprio falsificador 2 admite que
   um ganho só com dependências perfeitas não demonstra a tese conversacional. O microteste de mecanismo tem de ser
   seguido por extracção real antes de qualquer alegação.
2. O fragmento lógico é positivo e acíclico; negação, defeasibilidade e ciclos ficam fora — memórias reais têm os
   três. Não fingir cobertura.
3. Hiperarestas + versões + tempos bitemporais = disciplina de dados pesada antes de um ganho mensurável. Sequência
   obrigatória: M2 (feito) → M3 com Fu-R como schema → B2 como controlo → só então F.
4. O custo das intervenções `U(K sem f)` exige remover também derivados; se não, a intervenção não aconteceu.

## 4. Decisão de integração no programa "Fu 2" (renomear para "Fu-R/2")

| Fase | Antes | Agora |
|---|---|---|
| 72 (M3) | afirmações tipadas com peso de evidência | objectos E/C/R de Fu-R: afirmação bitemporal com modalidade e fontes; justificação com premissas AND/OR e tipos (suporte, pré-requisito, conflito, substituição); revisão localizada preservando justificações alternativas; validade avaliada no tempo da pergunta; peso de evidência em log-odds como força de suporte; entidades com IDs; slots antigos como vistas |
| 73 (eficiência) | inalterada | inalterada (Fu-R não a cobre) |
| 74 (bench relacional) | 4 braços (sem memória / cosseno / cosseno+ledger / +Fu) | braços B0/B1/B2/F de Fu-R + conjunto relacional reservado + STALE (revisão implícita); falsificadores §11 pré-registados; contar extracção e manutenção no custo; o controlo forte é B2, não B0 |
| 75 (AGI) | runbooks, prospectiva, abstenção, bandit | idem + `G`/`I_Fu` offline com o grader como estimador barato e "desconhecido" por defeito |
| 76 (escala) | 100k pontos + ablação de sonhos | idem, com sonhos redefinidos como manutenção orçamentada de Fu-R (propor relações, verificar dependências, reconstruir derivados) |

Percentagens: a análise não as move (nada foi medido). Move o alvo: "originalidade > 60%" passa a significar
"H-Fu vence B2 em tarefas reservadas com custo total contado"; sem isso, o máximo honesto é engenharia de proveniência
bem feita (~45%).
