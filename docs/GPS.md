# GPS no Hackomon — 0.10.1

O Hackomon consulta o GPSd local da Hak5 em `127.0.0.1:2947`. Nao abre a porta
serial, nao muda baud rate, nao reinicia servicos e nao troca o modo escolhido
em Settings > GPS. O modo Native direto do pineapd ainda nao tem adaptador no
Hackomon; para esta integracao use o modo GPSd da Hak5.

## O que mudou

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

1. Feche o Hackomon, instale a 0.10.1 e mantenha o modo GPSd em Settings > GPS.
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
A causa exata e a estabilidade da 0.10.1 em movimento ainda precisam do teste
no Pager; nao ha confirmacao de correcao fisica apenas pelos testes de bancada.
