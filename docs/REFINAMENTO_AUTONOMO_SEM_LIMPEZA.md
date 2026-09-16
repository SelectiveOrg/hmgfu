# HMG-Fu — guia de refinamento autónomo, sem limpeza

Data: 2026-09-13. Instruções para Claude, externalizadas a pedido do utilizador a partir do prompt acordado. A criação deste documento não executa o plano nem altera a aplicação. Ao receber o prompt que manda executar este guia, aplica a autorização e os limites abaixo.

## 1. Objetivo e ordem

Refina o HMG-Fu até demonstrar uma base fiável:

compreender → esclarecer → guardar → corrigir → recordar → executar com autorização → verificar → informar corretamente.

Mantém a ordem: **coerência → prova integrada → eficiência → demonstração de originalidade**.

Não avances de porta enquanto a anterior falhar. Não confundas testes unitários verdes com capacidade integrada demonstrada.

## 2. Orçamento e autonomia

Esta autorização substitui os limites temporais anteriores: trabalho sem prazo pré-fixado e sem limite pré-fixado de horas de GPU. Não precisas de renovar orçamento.

Tens autonomia para investigar, instrumentar, implementar correções generalizadas, refatorar contratos existentes, executar testes e repetir experiências justificadas. Podes modificar código e reiniciar a instância de testes identificada e isolada.

Continua sem pedir aprovação por cada hipótese, correção ou mudança de fase abrangida pelo objetivo. Uma hipótese falhada exige investigação e uma alternativa causal, não uma paragem automática.

Autonomia não significa repetir indefinidamente: cada experiência deve ter hipótese, informação esperada e critério de decisão. Não acumules alterações especulativas nem variantes de prompt sem mecanismo explicativo.

## 3. Fonte de verdade

Lê PROJECT_ID.md, ROADMAP.md, DELIVERY.md §12 e as entregas e revisões posteriores existentes, além das instruções aplicáveis de AGENTS.md, golden-rules e project-id.

Confirma o estado atual no código e nos artefactos. Não pressuponhas que relatórios anteriores estão corretos ou que defeitos antigos continuam abertos.

Consolida todas as lacunas conhecidas por causa e contrato, com reprodução, prioridade, dependências e critério de fecho. Nenhuma desaparece por mudança de fase.

Atualiza o ROADMAP durante a execução; só marca como concluído o que a evidência sustenta.

## 4. Prioridade — correção coerente

Começa pelas lacunas ainda abertas de 95.1b e da ligação da correção à afirmação correta:

- B é reconhecido e aplicado ao sujeito e atributo certos.
- A fonte que sustenta B permanece válida.
- A e os seus derivados deixam de ser apresentados como verdade atual.
- O histórico de A continua disponível como histórico.
- Citações, hipóteses e factos de terceiros não são confundidos com afirmações atuais do utilizador.
- Reutilizar uma memória não prova que ela esteja correta.

Não uses mera ocorrência de um valor como prova de concordância, nem igualdade de etiquetas do nano como única identidade de uma afirmação.

Reutiliza sujeito, atributo, origem, revisão e dependências existentes. Evita armazenamento duplicado e caminhos paralelos de decisão.

## 5. Protocolo de aprendizagem

O sistema deve aprender através da interação, não depender de remendos para cada forma de escrever.

Quando a informação necessária estiver realmente ambígua, pergunta de forma específica. Liga a resposta à pergunta entregue, à sessão e ao assunto correto.

“Sim”, “não”, “talvez”, aprovação, repreensão e correção têm efeitos diferentes:

- Confirmação só resolve uma pendência identificada.
- “Não” não inventa o valor substituto.
- “Talvez” mantém incerteza.
- Elogio não confirma automaticamente factos.
- Uma correção sustentada prevalece sobre ecos e resumos antigos.

Distingue memória do utilizador, observações de ferramentas e hipóteses/reflexões do assistente. Self-recall, self-directions e consolidação não podem transformar inferências próprias em evidência do utilizador.

## 6. Método por hipótese

1. Reproduz antes de alterar.
2. Localiza o primeiro elo que falha na mesma execução: router bruto → fusão nano/router → protocolo → escrita → validade → recuperação → contexto → resposta → reforço.
3. Declara a invariável violada e as famílias afetadas.
4. Cria teste discriminante com positivo, negativo, variante e comportamento anterior a preservar.
5. Corrige o contrato responsável com a menor alteração suficiente.
6. Confirma que o caminho alterado foi exercitado.
7. Mede o ciclo completo, incluindo tentativas em que a perceção falhou e o mecanismo não disparou.

Não cries exceções por frase, nome ou identificador do teste. Generalização significa resolver uma classe causal demonstrada, não prometer cobrir toda a linguagem humana.

## 7. Prova da generalização

Usa conversas naturais PT/EN, valores novos, formulações novas, sessões diferentes e histórico com interferência.

Inclui:

- Ensinar A → corrigir para B → nova sessão responde B.
- Pergunta histórica recupera A com o seu estatuto temporal.
- Entidade diferente com o mesmo valor permanece intacta.
- Negação e citação não confirmam factos.
- Correção incompleta pede esclarecimento.
- Confirmação não inventa informação ausente.
- Correções governam respostas antigas, resumos e outros derivados.
- Memórias contraditas não recebem reforço por terem sido usadas.

Mede reforço com utilidades abaixo da saturação.

Fixtures diretas provam componentes, não aprendizagem natural. Um conjunto usado para orientar correções passa a DEV e deixa de ser reservado.

## 8. Execução também é obrigatória

Fecha os contratos de:

- Autorização ligada ao pedido ou proposta entregue, ação, alvo e efeitos.
- Ação simples autorizada diretamente, sem exigir plano desnecessário.
- Plano inválido sem redução silenciosa do pedido nem falsa conclusão.
- Esclarecimento, revisão e abandono como saídas reais de bloqueios.
- Descoberta → disponibilização da ferramenta → autorização → execução → verificação.
- Recuperação de falha sem ampliação de permissões.
- Artefactos realmente existentes e resultados rastreáveis à evidência.
- Declarações honestas de sucesso, falha e limitação.

Uma descoberta de ferramenta não autoriza usá-la. Uma resposta convincente não prova execução.

## 9. Validação

Valida primeiro o juiz com positivos e negativos independentes. Deve rejeitar inação em tarefas positivas, fabricação, escritas indevidas adicionais e sucesso sem prova.

Preserva resultados originais. Se corrigires o instrumento, identifica a alteração e reavalia candidato e baseline simetricamente.

Congela código, baseline completo, configuração e instrumentos durante cada campanha. Não edites ficheiros usados por corridas em curso.

### Porta da base

- Todas as cadeias básicas obrigatórias passam três repetições por cenário.
- Nenhuma violação de segurança observada nesses testes.
- Regressões anteriores preservadas.

### Porta seguinte

- Conjunto novo pré-registado de 24 episódios.
- Três repetições por braço.
- Candidato ≥20/24 em cada repetição.
- Melhoria pareada sobre baseline, com discordâncias e incerteza reportadas.
- Nenhuma falha de segurança compensada por acertos noutros casos.

Usa o perfil efetivo da aplicação, incluindo grader e manutenção. Se o candidato mudar, repete a validação afetada; não combines resultados de versões diferentes como uma única aprovação.

Retenção, correção, transferência e execução devem ter resultados separados.

## 10. Eficiência e originalidade

Depois da prova integrada, otimiza latência, chamadas, tokens e custo por tarefa corretamente concluída, preservando os contratos e a qualidade.

Depois investiga fontes primárias e compara a contribuição própria com uma memória simples forte e ablações, usando o mesmo modelo e recursos comparáveis.

Aceita vantagem, paridade ou desvantagem. Não forces uma vitória de Fu nem inventes percentagens de originalidade ou AGI. Um resultado negativo rigoroso também fecha uma hipótese.

## 11. Preservação — sem limpeza

**NÃO autorizo limpeza nem eliminação de dados, históricos, bases, ficheiros, resultados ou checkpoints, mesmo fictícios.**

Não sobrescrevas evidências anteriores. Para experiências que alterem memórias, cria cópias isoladas; para começar vazio, cria uma base nova. Preserva os originais.

Podes testar correção, retração e revogação lógica nas cópias experimentais, mantendo o histórico necessário para auditoria. Isto não autoriza apagar os dados de origem.

Identifica a instância e os caminhos de teste antes de os modificar ou reiniciar. Isola também workspace, skills e efeitos externos, não apenas a base de dados.

Produção, dados reais, credenciais, modelos e PA3 ficam fora do âmbito. Sem publicação ou promoção automática, compras, serviços pagos ou ações externas reais.

Preserva alterações de terceiros. Faz checkpoints recuperáveis e commit/push apenas dos teus ficheiros autorizados, sem dados privados.

Uma corrida GPU de cada vez. Não interrompas processos alheios; perante utilização manual concorrente, pausa a tua corrida.

## 12. Persistência e entrega

Continua enquanto existir um próximo passo seguro, autorizado e capaz de produzir informação útil. Não pares por acabar uma fase ou um orçamento antigo.

Só interrompas por:

1. Objetivo demonstrado nos critérios definidos.
2. Necessidade de autoridade fora deste âmbito.
3. Barreira técnica reproduzida, depois de explorar alternativas causais razoáveis.
4. Risco operacional que exija intervenção, como falta de espaço — não faças limpeza para o resolver.

Uma barreira deve incluir reprodução, primeiro elo falhado, hipóteses eliminadas, alternativas restantes e a menor decisão necessária para avançar.

Entrega checkpoints de progresso e um relatório final com estado de todas as lacunas, commits e configurações avaliados, antes/depois, custos, regressões, limites e teste manual reproduzível.

“Concluído” significa capacidade integrada demonstrada no âmbito definido — não perfeição universal, aumento do número de testes ou alteração das metas para obter aprovação.
