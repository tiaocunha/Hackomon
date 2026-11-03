# Proximas entregas

## Implementado na 0.8.8; validacao fisica pendente

- Painel local do WDGWars: todas as expedicoes, fila avulsa conciliada, ultimo
  lote aceito, linhas invalidas/incompletas e orientacao para retomar.
- Consulta fora da tela principal, sem bloquear os radios e sem enviar dados.
- Tres missoes com medalhas persistentes e frases/reacoes das dez familias.
- Mantidos XP sem teto diario, GPSd nativo e testes ativos apenas por selecao.

## Proxima validacao de campo

- Comparar XP, repeticoes, percurso e resumo em uma saida real.
- Fazer um envio escolhido pelo usuario ao WDGWars e conferir o recibo/contadores
  do servidor. Testes HTTP automatizados sao simulacoes, nao comprovacao de aceite.
- Conferir continuidade depois de uma queda/reinicio sem repetir lotes confirmados.
- Medir tempo de consulta com muitos CSVs no hardware, legibilidade e consumo.

## Ainda nao implementado

1. Diario navegavel de saidas e mapa simples com pontos GPS.
2. Mais missoes, afinidades de familia, itens e recompensas de colecao.
3. Perfis normal/economico, definidos apos medir bateria e memoria no Pager.
4. Melhor organizacao e comparacao de evidencias por atendimento; explicacoes
   e relatorio assistido para o cliente. A primeira versao nao exige IA externa.
5. Eventual assistente de IA para interpretar achados. Modelo, hospedagem,
   consumo e tratamento dos dados ainda nao foram definidos.

Nenhum item futuro nesta lista e apresentado como funcionalidade pronta.
