# Sincronizacao WDGWars — 0.7.0 experimental

## Uso na tela

Abra **Redes / Laboratorio → WDGWars: sincronizacao e conta**. A chave continua
local, em `/mmc/root/hackomon/config.json` (`wdgwars_api_key`, 64 caracteres
hexadecimais) ou `HACKOMON_WDGWARS_API_KEY`. Nao a envie pelo chat ou ao GitHub.
E necessario acesso a Internet ja configurado, Python SSL e certificados CA.

- **Validar chave e consultar conta**: consulta a conta e os totais informados.
- **Sincronizar expedicoes + fila**: envia descobertas pendentes de todas as
  expedicoes e, depois, o restante da fila rapida. A confirma o compartilhamento
  de nomes, enderecos, sinal e GPS antes de iniciar.
- **Enviar somente fila rapida**: usa apenas o snapshot de ate 500 registros.
  Um lote de expedicao ja pendente exige escolher expedicoes/repetir; essa opcao
  nao amplia silenciosamente a origem do envio.
- **Historico local**: CIMA/BAIXO pagina os ultimos 100 eventos desta chave.
- **Repetir envio incerto**: repete apenas o lote pendente, apos aviso de que o
  servidor pode ja ter recebido os mesmos registros.
- **Guardar lote pendente e liberar fila**: arquiva o estado local sem apagar
  o lote nem os originais. Nao confirma recebimento, nao cancela tarefa remota
  nem dispensa espera exigida pelo servidor. Um futuro envio pode repetir dados.

Durante sincronizacao, B solicita cancelamento depois da resposta em andamento;
nao interrompe o HTTP imediatamente. O timeout de rede e 15 segundos (nao e uma
garantia de duracao total da operacao). A descoberta da expedicao pode continuar:
uploads nao ocupam o bloqueio de radio. Registros que chegam depois do snapshot
nao sao removidos da fila quando um lote anterior e confirmado.

## O que entra no envio

Somente `expeditions/<uuid>/discoveries.csv` do Hackomon e os registros da fila
rapida explicitamente selecionada. O leitor verifica cabecalho WigleWifi-1.6,
colunas esperadas, tipo/endereco, coordenadas finitas, precisao, sinal e data UTC.
Campos sao serializados novamente por uma lista explicita de descoberta.
Linhas invalidas ou nomes `_nomap`/`_optout` sao contados como ignorados locais.

Nao existe envio generico de pastas/arquivos arbitrarios. Links simbolicos nas
origens sao recusados. PCAPs, senhas, dicionarios, trilhas GPS e relatorios de
clientes nao entram nessa leitura. O CSV original permanece intacto mesmo se
o servidor recusar linhas. Nenhum upload concede XP adicional.

## Lotes e retomada

O CSV completo e lido em lotes de ate 500 linhas, cada payload limitado a 1 MB.
Requisicoes sao sequenciais, com espera de um segundo entre lotes aceitos. O
limite de 500 da fila rapida deixa de limitar o total de dados da expedicao.
Uma execucao considera ate 500 expedicoes pendentes; outras ficam para a proxima.

Cada arquivo e considerado ate o tamanho observado no inicio daquele snapshot.
Novas linhas anexadas pelo coletor ficam para a proxima sincronizacao. Uma linha
final incompleta nao e enviada nem avancada no progresso. O app indica dados
novos/incompletos em vez de declarar tudo sincronizado.

Antes do POST, grava um payload privado e o estado `sending`. Somente depois de
uma resposta reconhecida, grava atomicamente o recibo, o proximo offset e o hash
do prefixo. Um lote confirmado nao e reenviado em uma retomada normal. Ao
retomar uma origem pendente, verifica o prefixo ja processado. Arquivo truncado/reescrito bloqueia
a origem para revisao, em vez de zerar automaticamente o progresso.
Um arquivo concluido com o mesmo tamanho e carimbo de modificacao e considerado
inalterado sem reler seu hash inteiro. Edicoes manuais de arquivos ja enviados
nao sao um fluxo suportado para solicitar correcao no servidor.

Payloads temporarios confirmados podem ser removidos depois de persistir o
recibo; os CSVs originais nunca sao removidos. Uma queda entre a aceitacao remota
e a gravacao local pode tornar o resultado incerto. Nao ha garantia de envio
exatamente uma vez: repetir explicitamente um lote incerto pode duplicar dados.
O cliente nao presume uma chave de idempotencia que a API nao documenta.

## Respostas e limites do servidor

O cliente usa somente `https://wdgwars.pl/api/me` e
`https://wdgwars.pl/api/upload-csv`, com `X-API-Key`. Recusa redirecionamentos e
respostas acima de 64 KB. A conta e validada antes de uma sincronizacao.

HTTP 200 precisa de `ok: true`, `success: true` ou contadores numericos conhecidos
(`imported`, `captured`, `merged_samples`), sem indicador explicito de erro.
HTTP 200 com corpo desconhecido nao confirma recebimento. "Envio aceito" conta
os itens do lote recebido; "Importados" usa somente o contador real devolvido,
ou mostra n/d. `no_gps`, `bad_rows` e ignorados locais permanecem separados; os
contadores do servidor podem ter semanticas diferentes e nao sao somados como
se fossem necessariamente registros distintos. Aceitacao nao garante pontos.

401/403 indicam problema de chave/permissao. 429 persiste `Retry-After` e bloqueia
tentativa antecipada; a interpretacao e limitada a no maximo sete dias. Nao ha
um loop automatico de repeticao: o usuario volta a sincronizar apos a espera.

Timeout, resposta desconhecida, erro de servidor potencialmente ambiguo ou
reinicio em estado `sending` preservam o payload e exigem **Repetir envio incerto**
para outro POST. HTTP 202 guarda o `job_id` quando valido, mas NAO avanca o
cursor como se houvesse importacao concluida. Nao ha consulta automatica a
endpoints de jobs nao documentados na API publica. Confira o servico antes de
repetir um job pendente; o aviso de repeticao existe porque ele pode ainda estar
sendo processado. O cliente envia lotes pequenos pelo endpoint sincrono.

Contrato consultado: [API publica WDGWars](https://wdgwars.pl/press).
Nenhum codigo de aplicativos de terceiros foi copiado para esta implementacao.

## Persistencia e chave de conta

Metadados privados ficam em `wdgwars/<hash-da-chave>.json`; payloads pendentes em
`wdgwars/outbox/<uuid>.csv`. Usam permissoes privadas quando o sistema suporta.
O hash separa os checkpoints por chave; a chave original nao entra no historico.
Alterar/rotacionar a chave inicia outro conjunto de checkpoints, mesmo quando a
conta e a mesma, e pode ocasionar reenvio apos confirmacao manual. Originais
retidos e payloads arquivados usam espaco local e nao sao limpos em massa.

O historico guarda fonte, horario UTC, estado, quantidade e contadores, sem
nomes de rede, coordenadas, chaves ou senhas. Na tela: N=itens do envio,
I=importados informados, G=sem GPS informado, B=linhas invalidas informadas,
L=ignorados locais. O historico e local; nao substitui o historico da conta no site.
Um manifesto invalido e preservado e bloqueado, nao reinicializado silenciosamente.
Use uma instancia do Hackomon por diretorio de dados.

## Validacao e pendencias

Testes automatizados usam respostas HTTP/arquivos simulados. Cobrem expedicao
acima de 500 registros, retomada, cancelamento, erro de disco depois do POST,
timeouts, 202, 429, schema desconhecido, descarte GPS/optout, arquivo incompleto,
alteracao de prefixo, separacao de chave, protecao de origens e fluxo completo
da tela sem bloquear o radio. A conta real e o hardware ainda precisam de teste.

Envio automatico por conectividade, polling de jobs remotos, sincronizacao com
o telefone, redefinicao de cursores apos edicao manual e sincronizacao de badges
continuam pendentes. A integracao nao gerencia a conexao de Internet do Pager.
