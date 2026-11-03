# Expedicoes e modo hibrido — 0.6.0 experimental

## Implementado nesta entrega

Menu **Expedicao** com inicio, pausa, retomada, encerramento, companheiro animado,
contadores, distancia aproximada, XP e diario persistente offline. Um processo
de coleta alterna varreduras Wi-Fi passivas e descoberta BLE, enquanto outra
thread amostra o GPS externo. A renderizacao da tela de expedicao usa 4 FPS;
entrada e processamento continuam no loop normal. Nenhum ataque e selecionado
automaticamente pelo coletor.

As buscas sao ciclos limitados de ferramentas instaladas, nao captura continua
de todos os canais. A serializacao de radios prioriza compatibilidade nesta
primeira versao: apenas uma tarefa de radio do Hackomon roda por vez.

## Controles

- A: iniciar, pausar ou retomar. Depois de encerrar, inicia uma nova expedicao.
- ESQ: solicitar encerramento e aguardar o ciclo em andamento.
- DIR: congelar a lista de ate 100 APs recentes para selecionar um alvo autorizado.
- B: voltar ao menu do pet; a coleta continua. Sair do app pausa a expedicao.

No seletor, CIMA/BAIXO escolhe, ESQ atualiza a lista a partir da ultima busca,
A avalia o AP escolhido e B retorna. O alvo precisa ter sido visto nos ultimos
cinco minutos. A avaliacao usa o escopo temporario de um BSSID do modo Atendimento,
com captura EAPOL e teste offline PSK quando compativeis e disponiveis.

A selecao pausa a coleta e aguarda o ciclo que detem o radio. Ao terminar ou
falhar, retoma a expedicao que estava rodando. A pausa tambem interrompe o
registro de novos pontos da trilha; nao preenche a lacuna de cobertura. Nunca
retoma automaticamente um alvo de teste apos reiniciar o app.

Pausa/encerramento nao interrompem imediatamente uma ferramenta em execucao:
um ciclo pode levar cerca de 35 segundos. Uma avaliacao aguarda esse ciclo e
depois usa os limites do Atendimento (cerca de 90 segundos em falhas normais).
Cancelamento imediato e uma fila persistente de varios testes ficam pendentes.

## Localizacao e qualidade dos dados

GPSD local (127.0.0.1:2947) fornece TPV com horario UTC, modo >= 2 e erros
horizontais positivos <= 100m. A amostragem usa conexoes curtas aproximadamente
a cada segundo; falhas/conexao/fix podem reduzir a frequencia efetiva.

O buffer guarda ate 120 fixes. Wi-Fi usa o horario estimado a partir de `last
seen: N ms ago` fornecido por iw, com resolucao de segundos. BLE usa o instante
de recebimento da linha RSSI do bluetoothctl. Um fix so e associado se sua
diferenca temporal for <= 3 segundos. Estes sao horarios estimados pela ferramenta,
nao timestamps garantidos de recepcao do pacote no radio. Bufferizacao do BlueZ
e processamento podem introduzir erro adicional. O CSV usa a precisao reportada
pelo GPS e nao expressa todo esse erro de sincronizacao.

Sem idade Wi-Fi ou fix proximo, a descoberta permanece local como sem GPS e
fica fora do CSV/XP de mapeamento. O modo antigo de busca pontual com GPS mantem
seu proprio limite estacionario; a expedicao usa o buffer temporal e aceita
movimento. Saltos com velocidade media > 70m/s ou lacunas > 15s nao contribuem
para distancia. Pequenos movimentos abaixo da margem do GPS sao filtrados.
Distancia nao equivale a odometria exata nem a uma rota navegavel.

## Persistencia, limites e recompensas

Cada expedicao possui um UUID e arquivos privados em `expeditions/<id>/`:
`summary.json`, `track.jsonl`, `observations.jsonl`, `discoveries.csv` e
`audits.jsonl`. Ao encerrar, gera `summary.txt` em portugues. `current.json`
aponta para a ultima expedicao. Reiniciar restaura o diario pausado; A retoma
explicitamente. Pontos/observacoes sao anexados em disco; o resumo usa gravacao
atomica, com checkpoints por lote e a cada dez fixes. Uma interrupcao pode
deixar o ultimo resumo atrasado em relacao aos arquivos anexados.

Identidades distintas sao limitadas a 10.000 por expedicao. Um mesmo endereco
gera novo registro depois de 60s, movimento >= 30m ou ao ganhar localizacao que
antes faltava. Isso nao aumenta o XP por repeticao. Nomes `_nomap`/`_optout` sao
excluidos do diario de descobertas e do CSV. A trilha GPS ainda representa o
percurso; zonas privadas de exclusao geografica nao foram implementadas.

Limites locais: observacoes 20 MB e trilha 10 MB; ao atingir um deles a coleta
pausa, para o usuario encerrar e abrir outra expedicao. Um lote em andamento
pode exceder um pouco o limite de observacoes. A fila de eventos entre threads
e limitada a 128; o resumo encerrado registra eventos descartados se houver
sobrecarga. O diario e limitado; nao representa armazenamento infinito.

XP usa as regras atuais: novos enderecos localizados valem 2 XP Wi-Fi/1 XP BLE,
com teto global de 120 XP de descoberta por dia. O pet reage com felicidade ao
ganhar XP e mostra pose triste sem GPS recente quando estiver ocioso. Formas,
cuidados e evolucoes existentes continuam. Afinidades, novos ovos por expedição,
itens e ramificacoes evolutivas ainda sao propostas futuras.

## Testes e compartilhamento

O escopo de captura continua sendo somente o AP escolhido do laboratorio/cliente
autorizado. Recursos de monitor temporario, limites de captura/dicionario e
limpeza sao os do modo Atendimento. Captura EAPOL e recuperacao confirmada sao
estados separados. Protocolo desconhecido, falta de dicionario e captura
insuficiente sao resultados inconclusivos ou nao executados. Nao ha IA ou
processamento remoto nesta versao. Os testes detalhados ficam em `visits/` e
as capturas/resultados secretos em `lab/`, separados da descoberta exportada.

A fila global de upload continua limitada a 500 observacoes. CSV local da
expedicao preserva os registros adicionais e pode ser importado pelo Wardrive
Go (compatibilidade ainda precisa de validacao no aplicativo real). O envio
manual ao WDGWars usa a fila global e a chave local; nao envia automaticamente
todo o CSV da expedicao, capturas, senhas, trilha ou relatorios do cliente.
Envio em lotes do arquivo completo e sincronizacao movel ao vivo ficam pendentes.

## Validacao

Testes de desktop usam radios/GPS/processos simulados. Verificam associacao por
horario, GPS ausente, movimento, saltos, retomada pausada, deduplicacao, fila
cheia, isolamento de evidencias, exclusao optout, serializacao de radio e fluxo
da tela ate a avaliacao do alvo. Eles nao provam compatibilidade de driver,
autonomia, posicoes corretas durante um percurso real ou quebra de senha real.
Veja `HARDWARE_VALIDATION.md` e `LEIA_PRIMEIRO.txt` no ZIP antes do primeiro teste.
