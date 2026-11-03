# Hackomon: companheiro de wardriving e assistente de pentesting

Status: conceito aprovado e especificacao futura. Este documento nao adiciona
funcionalidades executaveis a versao 0.5.0. Data: 2026-11-03.

## Identidade

O Hackomon acompanha expedicoes, reage a descobertas reais, acumula historias
com o usuario e evolui. Tambem ajuda a organizar e executar avaliacoes de redes
no laboratorio e em atendimentos autorizados. Os dois usos compartilham o pet,
o diario e a interface, com evidencias e resultados identificados por sessao.

## Expedicoes

- Iniciar, pausar, retomar e encerrar uma expedicao na tela do Pager.
- Coleta continua de descobertas Wi-Fi/BLE, com operacao offline.
- Associar cada observacao a um horario e a uma posicao validada do GPS externo.
  A qualidade de um fix atual nao valida retroativamente observacoes antigas.
- Guardar percurso, registros novos, diversidade, marcos e estado da fila.
- Aplicar deduplicacao, limites de recompensa e exclusoes de mapeamento.
- Mostrar reacoes curtas do pet, adequadas a uma tela 480x222 e ao consumo medido.
- Encerrar com um diario de descobertas e progresso, preservando registros em
  caso de interrupcao. Sem sinal de GPS, indicar a limitacao e separar registros
  sem localizacao; nao inventar coordenadas ou distancia.

## Modo hibrido: testes de senha durante wardriving

Requisito adicionado: uma expedicao pode incluir captura e tentativa offline de
recuperacao de senha de redes autorizadas, mesmo que a execucao local seja lenta
ou precise ser adiada. A descoberta de uma rede nao concede escopo de teste.

Fluxo proposto:

1. A expedicao descobre redes e as apresenta na tela.
2. O usuario escolhe um AP do laboratorio/cliente autorizado para a sessao,
   sem digitar MAC ou cadastrar previamente uma rede. O nome sozinho nao inclui
   todos os APs de mesmo SSID, nem redes vizinhas.
3. O assistente verifica protocolo anunciado, recursos disponiveis e
   compatibilidade do teste. Um anuncio de seguranca nao prova vulnerabilidade.
4. Com recurso de radio disponivel, agenda a captura passiva apenas desse alvo.
   A presenca de EAPOL e a existencia de um handshake utilizavel sao estados
   diferentes. A reconexao normal de um cliente autorizado pode gerar a troca.
5. Uma evidencia adequada pode gerar um trabalho offline, com dicionario local,
   limite de tempo/recursos e cancelamento. O suporte atual de laboratorio a
   WPA/WPA2-PSK e o ponto de partida; outros protocolos exigem implementacao e
   validacao proprias. Captura nao garante recuperacao de senha.
6. O trabalho pode rodar no Pager quando viavel, ficar pendente ou ser executado
   em um computador local do usuario por uma integracao futura. Nenhum servico
   remoto de quebra ou modelo de IA esta implementado.
7. O pet recebe o resultado real e o diario registra evidencias, limites e
   recomendacoes. Um resultado inconclusivo nao comprova seguranca da senha.

Escopo de teste e uma selecao explicita da sessao. Nao existe neste conceito uma
rotina de tentativa de invasao contra todas as redes encontradas no percurso.
O assistente nao amplia o escopo automaticamente a partir de proximidade,
intensidade de sinal, fabricante ou nome da rede.

## Agendamento e recursos

- Descoberta, captura e trabalho offline precisam de um coordenador de tarefas.
- Havendo radios independentes e suporte confirmado, a descoberta pode continuar
  durante uma captura. Sem isso, alternar tarefas e informar as lacunas de coleta.
- Evitar que uma captura dedicada seja apresentada como cobertura continua de
  todos os canais. Registrar frequencia e janela efetivamente observadas.
- Adiar tarefas pesadas conforme limites configurados e condicoes medidas do
  dispositivo. Nao prometer velocidade ou autonomia sem testes fisicos.
- Permitir cancelar e aguardar a finalizacao/limpeza antes de liberar um radio.
- Recuperar trabalhos interrompidos sem retomar silenciosamente um teste de
  radio cuja autorizacao da sessao terminou.
- Exibir estados claros: pendente, executando, captura insuficiente, dependencia
  ausente, protocolo incompativel, limite atingido, cancelado ou senha recuperada.

## Companheiro, afinidades e colecao

Reacoes previstas: curiosidade com a primeira descoberta, entusiasmo com uma
sequencia de novidades, orientacao confusa quando o GPS fica impreciso e uma
comemoracao ao concluir a expedicao. O comportamento deve funcionar com poucos
frames e permitir reduzir alertas/animacoes.

Afinidades propostas: explorador, especialista Wi-Fi, especialista Bluetooth e
cartografo. Diversidade, qualidade dos registros e marcos podem influenciar
ornamentos, animacoes, personalidade e caminhos evolutivos. Ovos e itens
virtuais podem ser desbloqueados por conquistas locais.

Recompensas devem distinguir descoberta, avaliacao concluida e recuperacao
confirmada. Tentativa inconclusiva nao vira senha recuperada no jogo. Repeticoes
da mesma evidencia nao geram XP ilimitado. Cuidado e descanso continuam fazendo
parte do vinculo com o pet; valores e limites novos ainda exigem balanceamento.

## Dados locais, Wardrive Go e WDGWars

O Pager mostra o companheiro e o resumo da expedicao. Exportacao de descobertas
em formato interoperavel permite aproveitar mapas e analise de percurso no
Wardrive Go. Uma conexao ao vivo com o telefone permanece uma proposta futura.

O envio ao WDGWars recebe somente registros de descoberta aprovados para
mapeamento. PCAPs, senhas recuperadas, dicionarios e relatorios do cliente ficam
fora dessa fila. Guardar credenciais da conta no dispositivo. Permitir revisar
exclusoes antes de sincronizar e manter historico de recebimento confirmado.
Conquistas do servico so devem ser concedidas a partir de resposta verificada.

## Sequencia de entregas e criterios de aceite

1. Expedicoes e GPS: validar trilha continua, horarios por observacao, perda de
   fix, deduplicacao, interrupcao e persistencia offline no hardware.
2. Pet e diario: validar reacoes, resumo e XP; medir custo de renderizacao.
3. Coordenador hibrido: selecionar o alvo na sessao, confinar a captura, alternar
   radios quando necessario, cancelar e restaurar recursos mesmo apos falhas.
4. Teste offline: verificar captura incompleta, dependencia ausente, dicionario
   sem candidato, tempo esgotado e uma recuperacao conhecida de laboratorio.
   Garantir que evidencia/segredo nao entre na exportacao de wardriving.
5. Integracoes e colecao: validar a conta real, melhorar exclusoes e sincronizacao,
   e introduzir afinidades, ovos, itens e evolucoes por marcos.
6. Computador e IA: implementar protocolo local, protecao de evidencias,
   cancelamento e comparacao mensuravel de estrategias antes de prometer ganhos.

## Base existente e pendencias

Na 0.5.0 existem coletas pontuais com GPS, fila de descobertas, cliente WDGWars,
teste offline delimitado de laboratorio, inventario Bluetooth e atendimento
Wi-Fi com selecao dinamica. A suite tem 50 testes simulados; a validacao fisica
permanece pendente.

Expedicoes continuas, modo hibrido, coordenador de tarefas, aplicativo companheiro,
IA e as novas regras de afinidade/colecao descritas aqui ainda nao foram
implementados. Nao ha novo pacote executavel associado a este documento.
