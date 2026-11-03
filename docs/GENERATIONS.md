# Geracoes, ovos e ramificacoes — 0.10.0

Cada companheiro passa a ter uma vida de campo finita. A carreira do treinador
e o bestiario permanecem entre geracoes. Ha um companheiro vivo por vez.

## Entrada no sistema

Seu companheiro atual mantem XP, nivel, forma, cuidados, vinculo e medalhas.
Sua carreira de treinador comeca com o mesmo XP/nivel e compensacao da curva
anterior. Nenhum minuto antigo e convertido em idade ou incubacao.

Na primeira abertura de um save anterior, uma copia privada e criada em
`/mmc/root/hackomon/state.json.before-generations-v1`, sem substituir uma copia
ja existente. A migracao do save acontece ao abrir o app, nao no diagnostico de
instalacao. O instalador continua preservando save/config e o app anterior.

## Idade e fim de vida

Somente o tempo de **coleta valida** faz o companheiro envelhecer: os mesmos
intervalos aceitos para atividade na 0.9.0, com leituras recentes. Redes novas,
revisitas premiadas e redes conhecidas em recarga podem sustentar essa atividade.
Rotas repetidas contam; GPS nao e necessario para idade, ovos ou incubacao.

Pausas, app fechado, periodos sem leituras validas e grandes intervalos nao
somam idade. Os atributos de cuidado continuam usando as regras de desgaste
existentes; idade util e tempo de parede sao coisas distintas.

O relogio de fim de vida so comeca na fase adulta (estagio 3):

| Tempo de coleta desde adulto | Estado |
| --- | --- |
| 0 a menos de 8 horas | Jornada adulta |
| 8 a menos de 10 horas | Veterano, com postura e frase de envelhecimento |
| 10 horas | Fim do ciclo e registro no memorial |

Essa duracao e um valor inicial para teste. Nao garante a forma especial: os
requisitos de nivel, cuidado/vinculo e bem-estar continuam obrigatorios.
Filhotes/jovens que ainda nao chegaram a adulto nao consomem as 10 horas adultas.
Veterano e um estado de idade, sem adicionar outra criatura ao catalogo de 250.

Ao encerrar o ciclo, o pet deixa de ganhar XP/cuidado/evolucoes. Seu desenho
continua visivel em repouso ate nascer o sucessor. O treinador pode continuar
coletando XP e incubando o ovo. Nao existe reviver ou substituir um pet vivo.

## Ovo sucessor

Cada geracao prepara **um** sucessor:

1. Acumule 60 minutos de coleta valida, mesmo entre expedicoes.
2. Abra **Geracoes / Ovos -> OVO SUCESSOR** e escolha um dos ate tres ovos.
3. Acumule mais 20 minutos de coleta valida depois da escolha para incubar.
4. Apos o fim do ciclo atual, pressione A no ovo pronto e confirme o nascimento.

Um ovo pronto aguarda a despedida do companheiro atual. Se nao escolheu antes,
pode escolher/incubar depois da despedida continuando a expedicao. Sem escolha
nao existe nascimento automatico. As ofertas ficam salvas e nao mudam ao abrir
o menu novamente.

Ofertas usam linhas ainda nao nascidas, enquanto houver alguma das 50 faltando.
Uma linha visitada por ramificacao nao conta como ovo ja nascido. Quando todas
as 50 tiverem nascido, repetir linhas passa a ser permitido. Nao ha loja, compra,
resgate de codigos nem envio de dados para obter ovos.

O sucessor comeca como ovo, nivel 1, zero XP/cuidados/vinculo e atributos iniciais.
Recebe a afinidade predominante do anterior como heranca: um pequeno peso (+2)
nas sugestoes evolutivas, sem XP, niveis ou formas extras.

## Ramificacao na juventude

Ao cumprir os requisitos de filhote para jovem (nivel 8, cuidado + vinculo 10,
bem-estar 35), a evolucao espera sua escolha em **Geracoes / Ovos -> EVOLUCAO**.

Ha tres opcoes da mesma familia: continuar na linha atual e duas sugestoes.
Exploracao, sintonia e companheirismo influenciam a ordem das sugestoes. Pontos
de afinidade vem de distancia aceita, descobertas/revisitas premiadas, vinculo
e cuidados. Nenhuma opcao exibida exige um equipamento ou rede rara adicional.

A mostra a confirmacao; B cancela. Apos confirmar, o jovem, adulto e especial
seguem a linha escolhida. Os requisitos normais continuam obrigatorios. Todas
as formas visitadas ficam no bestiario permanente. Quem ja era jovem/adulto/
especial antes da atualizacao conserva a linha atual, sem escolha retroativa.

## Treinador, companheiro e memorial

O cabecalho mostra **TR** (nivel do treinador), seu XP permanente e **PET**
(nivel do companheiro). O rodape inicial mostra o XP que falta ao pet para
o proximo nivel. Cada ganho alimenta a carreira e, enquanto vivo, o pet ativo.
Ambos usam a curva crescente da 0.9.0 e chegam ao nivel 100; XP nao tem teto diario.

No nascimento, permanecem a carreira, bestiario, medalhas da carreira, linhagens
ja nascidas, historico de redes, cooldowns de seis horas, fila e recibos WDGWars.
Recibos de bonus da expedicao tambem permanecem, para o nascimento nao repetir XP
do trajeto anterior. Medalhas individuais e cuidados recomecam no sucessor.

O memorial registra geracao, forma final, nivel/XP do pet, tempo ativo, distancia,
descobertas/revisitas premiadas, medalhas e afinidade deixada. Guarda os **200
registros detalhados mais recentes** para limitar memoria; o total de geracoes,
linhas nascidas, carreira e bestiario permanecem mesmo apos essa janela.

## Controles e limites de validacao

Abra **Geracoes / Ovos** no menu inicial. ESQ/DIR muda entre VIDA, OVO SUCESSOR,
MEMORIAL e EVOLUCAO. CIMA/BAIXO seleciona; A executa/abre confirmacao; B volta.
Coleta pode continuar durante a consulta. Escolhas de ovo, nascimento e evolucao
sao salvas; operacoes de nascimento/ramificacao pedem confirmacao na tela.

Os testes simulam todo o ciclo sem esperar dez horas reais, incluindo reinicio,
preservacao da carreira, backup, falha de gravacao e limites das telas. O ciclo
real, ritmo de vida, memoria/bateria e visual no Pager ainda precisam de campo.
Nenhum teste de rede ou upload e iniciado por envelhecer, evoluir ou nascer.
