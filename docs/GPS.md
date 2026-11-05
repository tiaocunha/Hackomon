# GPS no Hackomon — 0.10.4

## Liberacao da interface e saida limitada — 0.10.4

A 0.10.3 preservou PineAP/GPSd e recebeu 64 TPV e 33 SKY com o app aberto,
mas nao passou no teste fisico de saida. Foi necessario encerrar o app preso
e recriar somente a interface visual; o menu voltou com os mesmos processos
GPSd/PineAP. Todos os TPV daquela amostra estavam sem fix de satelite.

A 0.10.4 usa esse mecanismo desde a abertura: remove somente a instancia
visual do supervisor procd, sem chamar o gancho `pineapplepager stop` que
para PineAP. Assim os arquivos de tela/entrada sao liberados. Ao sair, um
processo separado recria a interface por seu comando de inicio, sem reiniciar
GPSd/PineAP. A interface retorna como um processo novo. A tentativa anterior
de mante-la suspensa foi retirada.

O tratamento Python de interrupcao e restabelecido apos inicializar a biblioteca
de tela. Se o app nao responder a uma solicitacao de encerramento, o processo
de protecao limita a espera antes de encerrar somente o grupo do app. Saves
atomicos anteriores ficam preservados; uma saida forcada pode perder alteracoes
ainda nao salvas. Teste fisico de botoes, saida e GPS em movimento permanece
necessario para esta versao.

## Tentativa anterior substituida — 0.10.3

A leitura de 2026-11-05 confirmou o USB presente, GPSd sem processo/porta e a
API GPS da Hak5 desconectada naquele instante. Isso nao reproduziu o fix que o
usuario havia visto na tela. Os arquivos instalados coincidiam com a 0.10.2.

Foi encontrada uma incompatibilidade concreta no iniciador: ele chamava
`/etc/init.d/pineapplepager stop` para liberar a tela. No firmware instalado,
o `stop_service()` desse script tambem para PineAP e o remove do supervisor.
Esse efeito sobre o backend nao havia sido considerado nas versoes anteriores.

A 0.10.3 suspende somente o processo visual reconhecido, usando sinais do
Linux, e o devolve ao sair. Um processo separado protege a devolucao da tela
se o app falhar. Nao chama stop/start/restart dos servicos da Hak5 e nao muda
GPS, baud rate ou configuracao. O GPSd ainda precisa estar funcionando antes
de abrir o app; esta alteracao nao promete corrigir uma falha independente do
servico nem implementa um leitor direto da porta serial.

Os 229 testes de bancada passaram, incluindo isolamento de PineAP/GPSd,
identidade do processo visual, erros e encerramento. A continuidade real do
GPS, o desenho/botoes e o retorno da interface precisam do teste no Pager.

## Correcao da tela e verificacao do instalador — 0.10.2

O historico do aparelho mostrou uma posicao aceita pelo leitor com GPS 1,01 s
a frente do Pager e erro estimado de 34,77 m. A tela exigia diferenca positiva
no sentido oposto e mostrava "sem posicao recente" para esse fix aceito.
Agora a tela usa a mesma janela simetrica de 15 s do leitor e sinaliza pequenos
adiantamentos como `posicao recente (GPS +2s)`. Esse valor e arredondado para
cima apenas na exibicao; o horario original usado para mapear nao e alterado.
O limite de 3 s entre observacao e fix, a precisao de 100 m e as regras de
percurso continuam. Uma recusa recente continua prevalecendo sobre um fix velho.

O instalador agora consulta uma posicao pelo leitor do app e relata o motivo
da recusa, erro em metros e diferenca GPS/Pager quando disponiveis. Falta de
fix continua sendo opcional e nao impede instalar/jogar. Nao abre tela nem
porta serial, muda servicos, faz buscas ou inclui coordenadas na mensagem.

Na comparacao de 30 s, ambas as formas de ler GPSd receberam zero receptores
e nenhum TPV. O usuario confirmou depois que tinha retirado o GPS ao voltar;
isso explica aquela amostra e nao comprova desconexao durante a caminhada.
O teste nao demonstrou vantagem de uma conexao continua sobre a atual. Esta
atualizacao corrige a inconsistência confirmada da tela; estabilidade e eventuais
interrupcoes de dados durante movimento ainda precisam de teste fisico.

Apos o usuario reconectar o GPS, o instalador ainda recebeu lista vazia do
GPSd. Uma recuperacao separada verificou porta serial presente, GPSd habilitado
e modo direto desativado antes de reiniciar apenas o servico nativo existente.
O reinicio terminou com codigo zero. Em 15 s reapareceram um receptor, 30 TPV
e 15 SKY; todos os TPV estavam em modo 1, sem fix. Isso confirma a volta da
comunicacao, nao uma posicao utilizavel nem estabilidade durante movimento.
Se ocorrer "GPSd sem receptor" apos tirar/recolocar o GPS, com ele conectado
use Settings > GPS > Restart GPSd no modo GPSd. O app nao reinicia servicos
automaticamente nem muda para outro modo de leitura.

O Hackomon consulta o GPSd local da Hak5 em `127.0.0.1:2947`. Nao abre a porta
serial, nao muda baud rate, nao reinicia servicos e nao troca o modo escolhido
em Settings > GPS. O modo Native direto do pineapd ainda nao tem adaptador no
Hackomon; para esta integracao use o modo GPSd da Hak5.

## Compatibilidade implementada na 0.10.1

- Aceita `eph`, erro horizontal em metros, alem do par `epx`/`epy`. Quando ha
  mais de uma estimativa, usa a maior. Valores ausentes, nao finitos, zero,
  negativos ou acima de 100 m continuam sem servir para mapear.
- Combina campos de mensagens TPV parciais somente quando o identificador de
  receptor e o instante GPS sao exatamente iguais. O cache tem no maximo oito
  instantes; perda de fix ou lista de receptores vazia limpa o cache.
- A leitura de linhas fragmentadas tolera timeout temporario dentro de uma
  janela limitada. A idade e calculada no momento de cada mensagem usando o
  relogio do Pager. O relogio do PC nao participa dessa decisao.
- A tela Expedicao explica se faltou receptor, fix, horario, coordenada ou
  precisao. Divergencia de horario e precisao acima de 100 m tem mensagens
  proprias. Uma falha nova aparece mesmo se houve uma posicao valida ha pouco.
- O diario guarda `gps_health` e as ultimas oito mudancas de motivo em
  `gps_recent`. Esses campos contem apenas codigos/mensagens fixos, horario
  local do registro e numeros de modo, desvio de horario e erro estimado.
  Nao contem coordenadas, caminho serial, nomes de redes ou identificadores.
  O diagnostico usa o mesmo leitor instalado e inclui esses motivos filtrados.

O protocolo GPSd permite campos opcionais e varias mensagens TPV para a mesma
medicao; `eph` e uma estimativa de erro horizontal. Referencia:
[GPSd JSON protocol](https://gpsd.io/gpsd_json.html).

## Fix nativo e posicao utilizavel

"Fix established" na Hak5 confirma que o receptor tem solucao, mas nao prova
que o Hackomon recebeu todos os dados exigidos para localizar uma descoberta.
O app exige modo 2 ou 3, coordenadas finitas, horario UTC com diferenca de no
maximo 15 segundos para o Pager e erro horizontal entre 0 e 100 m (zero excluido).
Uma observacao so recebe coordenadas de um fix a ate 3 segundos do horario
original da descoberta. Nao se reutiliza indefinidamente a ultima posicao.

Qualidade em porcentagem, numero de satelites e HDOP nao sao convertidos em
metros de precisao pelo Hackomon. O `GPS_GET` nativo consultado retorna
latitude, longitude, altitude e velocidade; o quarto campo nao e precisao.

## Teste minimo

1. Feche o Hackomon, instale a 0.10.4 e mantenha o modo GPSd em Settings > GPS.
2. Com fix nativo, abra Expedicao e pressione A. Na pagina de sensores, confira
   a linha GPS durante uma caminhada curta.
3. Se o nativo mantiver fix e o app recusar, anote a mensagem. `DIAGNOSTICAR.cmd`
   coleta o motivo atual e o historico filtrado, sem enviar dados a servicos.

Wi-Fi/BLE continuam contando e rendendo XP elegivel sem GPS. Registros sem
posicao utilizavel nao viram pontos de mapa/upload. Nao e necessario ligar o
Wi-Fi Client Mode para consultar o receptor local.

## Validacao e limites

O usuario confirmou em 2026-11-03 que a Hak5 manteve fix enquanto o Hackomon
perdeu a posicao. Diagnosticos anteriores, feitos sem fix, mostraram GPSd com
lista vazia de receptores; nao demonstram a causa da falha durante movimento.
As mudancas de compatibilidade foram verificadas com mensagens simuladas.
A estabilidade da 0.10.4 em movimento ainda precisa do teste no Pager; nao ha
confirmacao de correcao fisica apenas pelos testes de bancada.
