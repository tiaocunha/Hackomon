# Progressao para rotas habituais — 0.9.0

O Hackomon passa a valorizar reencontros e atividade de campo, mesmo em cidades
com poucas rotas. Os pontos abaixo sao XP local do pet; nao alteram as regras
nem os pontos do WDGWars. Nao ha teto diario de XP.

| Atividade | Recompensa |
| --- | --- |
| Endereco Wi-Fi novo | 2 XP |
| Endereco BLE novo | 1 XP |
| Revisita a endereco conhecido, Wi-Fi ou BLE | 1 XP, apos 6 horas desde a ultima recompensa desse endereco/tipo |
| Cada 500 m adicionais contabilizados na trilha | 5 XP |
| Cada 10 minutos de coleta valida acumulada na mesma expedicao | 10 XP e 1 ponto de vinculo |

## Reencontros

O intervalo de 6 horas e individual por endereco/tipo e fica salvo. Pausar,
reiniciar o app, iniciar outra expedicao, obter GPS depois ou virar o dia nao
reinicia esse intervalo. Leituras repetidas no mesmo ciclo nao repetem XP.
O horario usado e o do Pager; o relogio do PC nao entra nessa regra.

Amostras precisam continuar recentes (ate 60 s), com endereco, tipo e sinal
validos. Opt-outs continuam excluidos. GPS nao e exigido para XP de descoberta
ou revisita, mas continua necessario para mapa/CSV/envio. A rotacao de enderecos
BLE pode contar o mesmo aparelho mais de uma vez; nao tentamos desfazer isso.

Saves antigos registravam apenas o dia da primeira recompensa. Para um endereco
premiado hoje, a primeira leitura na 0.9.0 inicia um intervalo conservador de
6 horas. Enderecos antigos usam o final daquele dia como referencia conservadora.
O app nao paga retroativamente todas as leituras feitas antes da atualizacao.

Os registros de enderecos e revisitas continuam limitados a 10.000 hashes cada
por memoria. Atingir esse limite nao impede revisitas ja registradas ou bonus de
atividade/percurso, mas impede adicionar novos enderecos ao registro cheio.

## Percurso e atividade

O bonus de percurso usa somente a distancia ja aceita pelo filtro GPS do diario.
Sem GPS, sem deslocamento contabilizado ou com salto rejeitado, nao inventa
distancia para premiar. Repetir a mesma rota em outra saida continua rendendo
porque o objetivo passa a ser o percurso realizado, nao apenas lugares ineditos.
Distancia continua aproximada e depende de precisao, amostragem e cobertura GPS.

Coleta valida significa receber observacoes recentes e elegiveis, novas ou
conhecidas. O tempo e somado entre essas amostras quando o intervalo e de ate
45 s. Pausa, ausencia de leituras, intervalo longo e tempo com o app fechado nao
somam atividade. GPS nao e obrigatorio. Ficar no mesmo local com leituras validas
pode render esse pequeno bonus de tempo; nao rende XP por cada leitura.

Fraçoes de tempo/distancia ficam na expedicao; uma nova saida comeca nova
contagem. Retomar a mesma saida preserva as fracoes sem contar o tempo pausado.
O tempo de atividade pode diferir do tempo total ativo exibido no resumo.
Ao atualizar uma expedicao antiga, blocos completos de percurso ja existentes
viram referencia inicial e nao sao pagos retroativamente.

Recibos dos blocos pagos ficam no mesmo save atomico do XP e do vinculo, para
evitar pagamento repetido ao reiniciar. O resumo discrimina XP por novas
descobertas, revisitas, atividade e percurso desde a 0.9.0; nao recalcula antigos
resumos nem pontos remotos.

## Niveis

O custo para sair do nivel L e chegar ao seguinte e **40 + 5 × (L − 1) XP**.
O nivel 1 comeca em zero. Ha 100 niveis; XP continua acumulando no nivel maximo.

| Passagem | XP necessario para a passagem |
| --- | --- |
| 1 -> 2 | 40 |
| 5 -> 6 | 60 |
| 10 -> 11 | 85 |
| 25 -> 26 | 160 |
| 42 -> 43 | 245 |
| 99 -> 100 | 530 |

O rodape da tela inicial mostra o progresso **dentro do nivel atual**, enquanto
o cabecalho continua mostrando seu XP total. Todos os ganhos, inclusive cuidados
e testes selecionados ja existentes, usam a mesma curva.

**Migracao sem perder progresso:** XP total, nivel ja conquistado, fracao de
progresso para o proximo nivel, formas, cuidados e medalhas sao preservados.
Uma compensacao interna de nivel e calculada uma vez para saves da curva antiga;
ela nao aumenta o XP exibido nem concede novas descobertas. Pequenas diferencas
de arredondamento podem ocorrer na fracao. O caso de 1.230 XP/nivel 42 continua
em 1.230 XP/nivel 42 e passa a precisar de 245 XP para chegar ao nivel 43.

## Evolucao e vinculo

Os requisitos combinam **cuidados + vinculo de campo**, sem exigir que voce
repita botoes de cuidado para acompanhar todo o progresso da expedicao.
Alimentar, brincar e descansar continuam recuperando os atributos do pet.

| Forma de destino | Nivel | Cuidados + vinculo | Bem-estar minimo |
| --- | --- | --- | --- |
| Filhote | 3 | 4 | 0 |
| Jovem | 8 | 10 | 35 |
| Adulto | 16 | 20 | 45 |
| Especial | 25 | 35 | 55 |

Cada 10 minutos de coleta valida concede 1 vinculo permanente. O tempo antigo
nao e convertido retroativamente. A tela Ajuda mostra os requisitos combinados;
nenhuma forma conquistada regride. Medalhas continuam sendo conquistas de
colecao e nao pagam XP extra.

Os testes de desktop cobrem limites das 6 horas, persistencia, pausas, intervalos,
recibos, migracao de todos os niveis antigos e o caso real de nivel 42. O ritmo
de progressao, precisao do percurso e legibilidade ainda precisam de teste em
campo na 0.9.0. GPSd, Recon, Blue5 e o firmware original continuam inalterados.
