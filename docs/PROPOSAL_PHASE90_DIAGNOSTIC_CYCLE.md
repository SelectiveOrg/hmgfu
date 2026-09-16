# Proposta — Fase 90: incorporar os diagnósticos A–E (Codex, 2026-09-07) nas próximas etapas

Estado: **proposta para aprovação do utilizador**. Não executada; não altera o objetivo (/goal) nem a ordem das prioridades. Escrita
depois do fecho da fase 89 (docs/PHASE89_KNN_ROUTER.md). Direcção do utilizador (2026-09-07): a prioridade é o mecanismo que faz a memória
funcionar correctamente; começa pelo diagnóstico das poucas escritas e pelo teste completo da lógica mensagem → informação estruturada →
memória relacionada → recuperação → resposta; nenhuma limpeza no caminho crítico; experiências preservadas para comparação; uma hipótese de
melhoria de cada vez. Cada etapa reutiliza um conjunto, bench ou telemetria já existente; nenhuma cria
um extractor, armazenamento, política de actualização ou camada de decisão novos. Cada experiência tem hipótese, orçamento e paragem fixados
aqui, antes de correr (restrição de simplicidade, ponto 4).

## 0. Ciclo central que a fase preserva

interpretar a mensagem (`sensitizer.extract` + router) → recuperar contexto (`retrieve.make_query_point`, `context_render`) → responder →
guardar/actualizar memória estruturada (`turn_tail` → `facts`/`assertions`/`fact_spans`). O sonho (`dream.py`) é manutenção opcional; nenhuma
etapa abaixo depende dele.

## 90.A — PRIMEIRO: autópsia das 3 escritas e de 20 chamadas sem escrita (fase 88)

- **Falha medida:** a fase 88 atribuiu a neutralidade do extractor a "os turnos quase nunca afirmam um facto na primeira pessoa" sem seguir
  as chamadas (errata registada no fecho da 89).
- **Porquê os componentes existentes não bastam:** os artefactos por item (`scratch/lme_peritem_88_W1.jsonl`) guardam só cat/qi/correct/
  reply/gold/error; `INGEST_COST` é um contador agregado. Não há registo por chamada do extractor.
- **O que reutiliza:** `ingest_session_like_agent` (harness 88.1) com `registry_span_extractor`; a amostra corre numa base descartável
  (`guard_scratch`). Acrescenta-se UM registo por chamada (mensagem → saída do extractor → `apply_spans` aceita/rejeita e porquê → escrita) no
  contador que já existe — sem novo sistema de log.
- **Regra de amostragem fixada antes de ler:** as 3 escritas + 20 chamadas sem escrita, 4 por categoria LME (KU, multi, ss-user, temporal,
  ss-assistant), a mais longa e a mais curta de cada categoria mais duas ao acaso com semente 20260907.
- **Classificação fechada:** nada memorizável · duplicado · informação legítima fora do contrato de perfil · falha de extracção · rejeição
  correcta · rejeição incorrecta · falha de persistência · evidência insuficiente.
- **Custo/paragem:** ≤ 23 chamadas do extractor (~0,7 s cada, < 1 min GPU); 30 min de análise + 15 min de reprodução. Ao atingir o limite,
  entrega a tabela com o que falta.
- **Entrega:** tabela dos 23 casos + UMA hipótese prioritária (a camada onde a próxima correcção entra).

## 90.B — Contrato mínimo do ciclo, mapeado ao código existente (sem código novo)

- **Falha medida:** nenhuma; é a página de responsabilidades que evita caminhos duplicados (ponto 3 da restrição).
- **Reutiliza:** `fact_spans.py` (contrato do extractor de spans), `facts.py` / `assertions.py` (valid/known time, retracção), `utterance.py`
  (idiomas, terceiros, passado), `turn_tail.py` (ordem regex → extractor → proveniência), `context_render.py` (secções entregues).
- **Entrega:** uma página: responsabilidade → módulo → implementado / ligado ao fluxo real / só proposto. Inclui o exemplo de contrato
  "Gosto de A" + "Ultimamente prefiro B" (conserva A, regista preferência relativa recente por B, não infere "odeio A", "ultimamente" não dá
  data) e onde cada parte já é (ou não é) coberta por teste. Custo: 0 GPU.

## 90.C — Teste completo do ciclo (24 conversas PT/EN): mensagem → informação estruturada → memória relacionada → recuperação → resposta

- **Falha medida:** nenhum conjunto existente é uma conversa curta com factos permitidos/proibidos, fontes esperadas e pergunta final
  (write_set v1–v7 = frases isoladas; truth core = unitário sem modelo; say-do = ferramentas; heldout m1–m5 = turnos/facts; LME = sessões
  longas). As famílias correspondem a defeitos já vistos: preferência A→B (rubricas da 85), terceiros (guarda em `fact_spans`), passado vs
  presente (`assertions.active(at=)`), informação distribuída entre sessões (LME multi), ficção/citação, pergunta sem evidência (abstenção).
- **O que cada conversa regista, por etapa do ciclo (a lógica do utilizador, medida ponta a ponta):** (1) mensagem; (2) informação
  estruturada produzida — extracção do turno (`query.extraction`) e saída do extractor de escrita (`fact_spans` / regex) com motivo de
  aceitação ou rejeição (`value_gate`); (3) memória relacionada — o que ficou no ledger/grafo, com proveniência e ligações (`link_episode`);
  (4) recuperação — os pontos e factos candidatos e o excerto realmente entregue ao leitor (`retrieved[].public()`, `injected_context`);
  (5) resposta — acerto semântico, afirmações não sustentadas, tempo até à resposta e até a memória estar utilizável (`tail_ms`).
- **Reutiliza:** o runner de conversas de `bench_say_do.py` (sessões, `--set`, clone), a telemetria por turno já existente (`timings`,
  `tail_ms`, `retrieved[].public()`, `injected_context`), `judge_admissible` para critérios semânticos, `derive_lme_pair.net_ci` para o
  emparelhamento. Novo: só o ficheiro de oracle `scripts/oracles/conv_v1.json` (24 conversas, 8
  famílias × 3, identificado como DEV) e um runner fino que reutiliza os anteriores.
- **Hipótese (fixada aqui):** a alteração escolhida em 90.A melhora ≥ 3 das 24 respostas finais sem degradação inspeccionada, com custo ≤ 1,25×
  da base. Como ±2/20 é o ruído do leitor registado, o Δ só se lê depois de ×3 repetições por configuração.
- **Piloto:** 6 casos sentinela (1 por família crítica) para verificar ligação e telemetria; se um componente não chega ao contexto, corrigir
  nessa camada antes do resto.
- **Custo/paragem:** piloto 15 min; comparação 24 × 2 configs × 3 reps ≈ 36–60 min de GPU, sozinha. Ao atingir o limite, guardar o
  incompleto e não contar itens não corridos como falhas.

## 90.D — Uma alteração, na camada que falhou (no máximo duas iterações)

- Só depois de 90.A nomear a camada. Se o facto não entra → extracção/contrato/validação (`fact_spans`, `value_gate`); se entra mas não
  aparece → recuperação/selecção (`retrieve`, `context_render`); se aparece e a resposta erra → leitor, com passagens de referência só como
  diagnóstico; se acerta mas demora → etapa dominante (a 89 já mostrou: o router modelo, ~1,5–1,8 s, não o embedding).
- Cada correcção: teste de regressão do defeito, uma camada, repetir só o diagnóstico relevante. Sem benefício após duas iterações → resultado
  negativo entregue, hipótese fechada.
- **Quatro perguntas** respondidas no ROADMAP antes de qualquer mecanismo (falha medida, porquê os existentes não bastam, o que substitui,
  como se mede).

## 90.E — Validação nova, uma vez, e decisão

- Congelar código/configuração; conjunto novo (não os itens 40–79 do LME já vistos nas 87/88; não os `conv_v1` de DEV): `conv_v2` reservado
  (autor-adjudicado, selado por commit, corrido uma vez) e, se a alteração tocar o leitor, itens LME 80–119 nunca usados.
- Controlo de semelhança por família contra qualquer base de exemplos (vizinho mais próximo por embedding, não só igualdade literal) — o
  controlo que a 89.4 acrescenta ao `decision_v2`.
- Entrega no formato de prestação de contas (§6 da proposta): pergunta, alteração única, casos/erros, ganhos emparelhados com dois exemplos,
  custo antes/depois da resposta e tempo até a memória estar pronta, decisão: adoptar / manter experimental / retirar / investigar.

## Ordem e disciplina de recursos

90.A → 90.B (página, 0 GPU, em paralelo com A) → 90.C piloto de 6 → 90.C completo (base actual, ×3) → 90.D uma alteração (a hipótese única
que 90.A nomear) → 90.C na alteração (×3) → 90.E. Uma hipótese de melhoria de cada vez; a GPU sozinha por corrida; nenhuma etapa de limpeza.

## O que não muda

O objetivo (/goal), a ordem das fases aprovadas e as três decisões pendentes do utilizador (janela 480, profundidade 20, candidato de
escrita) ficam como estão. Esta proposta entra no ROADMAP como Fase 90 só depois de aprovada.

## Apêndice — inventário das opções experimentais OFF (informação; FORA do caminho crítico)

Opções OFF acumuladas desde a 79, preservadas para comparação. Nenhuma remoção está planeada (direcção do utilizador: adiada salvo interferência ou risco comprovado). A coluna 'proposta' fica como registo para uma passagem de simplificação futura, quando o utilizador a pedir:

| opção | fase | evidência a favor de ficar | proposta |
|---|---|---|---|
| `knn_router_enabled` (+k, min_sim, módulo, bench flags) | 89 | G2 falhou; −1,6 s em ~17 % dos turnos, 0 na mediana | OFF; remoção adiada |
| `router_bypass_enabled` (pre_router determinístico) | 79.3 | reclama ~15 % a 1,000 nos conjuntos selados; não adoptado | remover ou fundir com o caminho único de decisão que 90.D escolher |
| `bypass_skips_nano` | 79.6 | depende do anterior | remover com ele |
| `nano_in_tail` | 80.2 | portas da 80 passaram sem custo de qualidade; não promovido | decidir: promover (menos chamadas antes da resposta) ou remover — a única com evidência positiva |
| `retrieval_limit_aggregate` | 86.1 | multi +3 [0, +7] em itens reservados | decisão do utilizador já pendente (profundidade 20) |
| `excerpt_max_chars` (janela 480) | 85/87 | KU 0,312 → 0,625 em itens reservados | decisão do utilizador já pendente (recomendado) |
| `fact_mapper_mode=spans` / `fact_mapper_role` | 84 | v7 0,947/0,592 vs 0,864/0,446; neutro no LME | decisão do utilizador já pendente |
