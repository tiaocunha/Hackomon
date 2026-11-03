# Missoes e companheiro de campo — 0.8.8

Na **Expedicao**, CIMA/BAIXO percorre **sensores -> resumo -> missoes**.
A coleta continua enquanto voce consulta essas telas. A inicia/pausa,
ESQ encerra, DIR continua abrindo a escolha de um alvo autorizado.

Tres medalhas iniciais:

| Missao | Objetivo na mesma expedicao |
| --- | --- |
| Primeiro olhar | Encontrar 10 enderecos novos elegiveis para XP |
| Dois mundos | Encontrar 5 enderecos Wi-Fi e 5 BLE novos elegiveis para XP |
| Passo explorador | Registrar 1 km de percurso aproximado com GPS valido |

As medalhas ficam no save do pet (`field_badges`), uma vez por objetivo.
O progresso fica no diario da expedicao e sobrevive a uma pausa ou reinicio.
O resumo de texto lista medalhas conquistadas naquela saida. Em expedicoes
antigas, a contagem das duas primeiras missoes comeca nesta atualizacao: nao
inventa descobertas novas a partir de contadores antigos. A distancia ja registrada
por GPS pode cumprir a terceira missao.

Medalhas nao acrescentam XP nem cuidado, nao liberam evolucao automaticamente
e nao tornam um endereco ja premiado elegivel outra vez. Repeticoes, amostras
antigas/invalidas e opt-outs nao avancam os objetivos de descoberta. A distancia
usa o mesmo filtro de saltos, precisao e pausas da trilha existente. Nao e um
odometro de precisao. Enderecos BLE aleatorios continuam podendo representar o
mesmo aparelho; o jogo nao tenta desfazer essa privacidade.

Cada uma das dez familias tem uma frase curta propria para descobertas novas.
O pet tambem reage a uma medalha, pausa e perda de GPS. Frases ficam visiveis
por alguns segundos ao lado do personagem, mantendo o resultado de XP no rodape.
Essas reacoes sao regras locais; nao ha modelo de IA, voz, consulta externa ou
mudanca no controle dos radios. Afinidades que alteram recompensas, missoes
diarias e novos desbloqueios ainda nao estao implementados.

Saves anteriores recebem uma colecao vazia de medalhas; XP, cuidados, evolucao,
configuracao e historico de redes sao preservados. Validacao visual e de uso
prolongado no Pager continua pendente para esta versao.
