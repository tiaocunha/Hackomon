# Hackomon 0.10.1: instalacao facil no Windows

0.10.1: compatibilidade GPSd com eph e mensagens parciais da mesma medicao;
linha GPS com motivo da recusa e diagnostico filtrado. Requer teste em movimento.
O save e mantido. Detalhes em [GPS](GPS.md).

0.10.0: Geracoes / Ovos, carreira permanente de treinador, vida util do pet e
escolha evolutiva. Seu pet atual e mantido, com idade ativa zero.

0.9.0: revisitas apos 6 horas, bonus de atividade/percurso, vinculo e nova curva de
niveis. XP/nivel/formas anteriores sao preservados. Detalhes em PROGRESSION.md.

0.8.8: no menu WDGWars, DIR abre pendencias de todas as saidas e ultimo recibo;
ESQ atualiza sem enviar dados. Na Expedicao, CIMA/BAIXO percorre sensores,
resumo e tres missoes com medalhas persistentes e reacoes do companheiro.
Enviar continua exigindo confirmacao. Esta versao requer validacao fisica.

Novidades: a Expedicao grava no CSV sem preencher a fila avulsa, explica XP
novo/ja premiado e mostra estados dos sensores. CIMA/BAIXO abre o resumo;
ESQ encerra. Para enviar a saida completa use WDGWars -> Sincronizar expedicoes
+ fila. O teto diario de XP permanece removido. A 0.8.7 ainda requer teste fisico.

Preparado para o seu **WiFi Pineapple Pager com Hak5 2.0.0-stable**.
App separado + tema Hackomon Field Companion. O firmware nao e substituido.
Os testes desta entrega foram feitos no computador: tela, botoes, radios, GPS,
desempenho e envio real ao WDGWars ainda precisam de validacao no seu Pager.

## 1. Prepare a conexao

Termine a configuracao inicial do Pager e crie a senha do sistema. Conecte-o ao
PC com um cabo USB-C **de dados**, ou conecte o PC ao AP de gerenciamento.
Ative SSH em **Settings > System > SSH** se estiver desativado.
Conecte o Pager a sua Internet pelo Wi-Fi Client Mode; confira data e hora.
O instalador usa a Internet do PC para a biblioteca e a do Pager para os pacotes.

Nao precisa abrir o PowerShell nem testar a conexao manualmente. O instalador
confere se o Pager esta acessivel antes de preparar o envio. Quando solicitado,
use a senha criada no primeiro inicio; os caracteres digitados ficam invisiveis.
O IP de gerenciamento e a conta sao os documentados pela
[Hak5 para SSH](https://documentation.hak5.org/wifi-pineapple-pager/connecting-to-the-wifi-pineapple-pager/ssh-and-the-wifi-pineapple-pager).

## 2. Instale pelo Windows

1. Baixe **hackomon-instalar-0.10.1.zip** e use **Extrair tudo** do Windows.
2. Na pasta extraida, abra **INSTALAR.cmd** com dois cliques.
3. Confira a identidade do Pager se aparecer a pergunta da primeira conexao
   e informe sua senha quando solicitado.
4. Aguarde **PRONTO!**. A janela permanece aberta para mostrar o resultado.

Deixe o Hackomon fechado durante a instalacao. Nao copie arquivos manualmente.
O instalador usa uma unica conexao SSH para transferencia e instalacao; assim
nao pede a senha novamente em cada etapa. A senha e tratada pelo OpenSSH,
sem ser lida, gravada ou enviada como argumento pelo script do Hackomon.
O atalho usa uma opcao de execucao PowerShell apenas nesse processo; nao muda
a politica permanente do Windows e os scripts locais podem ser lidos no ZIP.

O instalador:

- baixa **libpagerctl.so** diretamente do projeto PAGERCTL, em revisao fixa,
  e compara seu SHA-256 antes de enviar; o binario nao vem dentro deste ZIP;
- reutiliza a biblioteca ja baixada se o SHA-256 continuar correto;
- transfere os arquivos para `/mmc/root/hackomon-setup-0.10.1` em um pacote;
- instala Python 3 + ctypes **somente se faltarem**, pelos feeds que ja estao
  configurados no Pager, usando `opkg install -d mmc`;
- tenta instalar python3-sqlite3 no MMC se faltar o modulo para leitura do Recon;
- verifica importacoes e carrega a biblioteca sem abrir a tela;
- confere o iniciador a partir de uma copia temporaria, usando a pasta real
  informada pela Hak5, antes de apresentar a instalacao como concluida;
- instala o app em `/root/payloads/user/games/hackomon`;
- preserva um payload anterior em `/mmc/root/hackomon-backups/` e nao altera
  o save nem a configuracao em `/mmc/root/hackomon`;
- cria `/root/themes/hackomon-field` a partir do Wargames **local** do firmware.

Se um tema Hackomon 0.8.0 valido ja existir, a reinstalacao o confere e preserva
automaticamente. Uma pasta desconhecida ou um tema incompleto permanece intacto
e gera um aviso especifico, sem impedir que o app instalado seja identificado.

A base original e procurada primeiro em `/lib/pager/themes/wargames`, conforme
o [README oficial do Wargames](https://github.com/hak5/wifipineapplepager-themes/blob/master/themes/wargames/README).
Ela e somente lida; todos os arquivos personalizados ficam na nova pasta.

Nao atualiza em massa pacotes do sistema, nao troca feeds e nao instala drivers.
A instalacao de pacotes segue o destino MMC recomendado pela
[Hak5](https://documentation.hak5.org/wifi-pineapple-pager/external-packages).
A biblioteca fixada e de terceiros; integridade e API nao comprovam compatibilidade
com o firmware 2.0. Se o carregamento falhar, a instalacao para com o erro.

Para instalar novamente, basta abrir **INSTALAR.cmd** outra vez. Para uma
instalacao avancada que ignore o tema, ainda existe a opcao manual:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Instalar-Hackomon.ps1 -SkipTheme
```

## 3. Selecione o tema e abra o app

No Pager: **Settings > General > Theme > hackomon-field**.
Se o nome ainda nao aparecer, reinicie o Pager para atualizar a lista.
O tema muda o fundo do dashboard, a tela de bloqueio e a paleta; os outros
menus e icones sao herdados da sua base local. Isso preserva as funcoes da 2.0.
Ele nao substitui o tema interno do jogo nem adiciona animacao aos menus Hak5.

Abra **Payloads > Games > Hackomon** (algumas listas exibem tambem a categoria
User). O app usa a tela e os botoes diretamente. Nesta entrega, ainda para
temporariamente o servico da interface original e o reinicia ao sair; esse
comportamento precisa ser conferido no firmware 2.0. O launcher agora devolve
a interface antes de mostrar mensagens de falha.

## 4. Teste primeiro o essencial

1. Confirme tela horizontal, imagem inteira e leitura em 480x222.
2. Use o direcional, confirme uma acao de cuidado com A/verde e saia com B/vermelho.
3. Confira se o menu Hak5 voltou. Abra novamente e confirme o progresso salvo.
4. Confira dashboard, Theme, Settings, Recon e bloqueio/desbloqueio com o tema.
5. Se algo ficar errado, volte a **Settings > General > Theme > wargames**.

Se a interface nao voltar, pelo SSH:

```sh
/etc/init.d/pineapplepager start
```

Guarde a mensagem de erro e consulte `/tmp/hackomon.log`. Esse log e temporario
e desaparece no reboot. Nao publique config, capturas ou chaves junto do log.

## 5. GPS, expedicoes e Bluetooth

**0.8.6: XP de descoberta sem exigir GPS nem teto diario na Expedicao.** Cada
endereco Wi-Fi novo rende 2 XP; cada endereco BLE novo rende 1 XP. O progresso
anterior e mantido. O mesmo endereco/tipo nao paga novamente, mesmo apos
reiniciar, criar outra expedicao ou conseguir GPS. Descobertas antigas, sem
sinal valido, invalidas ou com sufixos _nomap/_optout nao pagam XP.

O save guarda hashes/datas para controlar essas recompensas, separado da fila
de mapa. Saves antigos preservam progresso e recompensas anteriores. Uma
descoberta sem GPS pode ser mapeada depois com fix valido, sem XP em dobro.
Sem GPS nao ha coordenadas, trilha ou registros enviados ao WDGWars.
Para atualizar, feche o Hackomon ate voltar ao menu Hak5; o instalador recusa
alterar o app aberto para preservar o progresso.

**0.8.4: compatibilidade com os dados observados no firmware 2.0.0-stable.**
O leitor aceita frequencias como `2437.0` no iw e BSSIDs BLOB ASCII no Recon.
O Wi-Fi automatico prioriza registros recentes do Recon antes de tentar uma
busca separada. Para Bluetooth, quando existe `/root/recon/blue5.db`, le os
anuncios LE recentes do Blue5, sem iniciar bluetoothd nem disputar o controlador.
Registros classicos/transportes desconhecidos nao sao classificados como BLE.
Blue5/logging precisam estar ativos; dados antigos nao viram descobertas atuais.
Sem Blue5, permanece a alternativa legada via bluetoothctl. O doctor mostra
quantos registros nativos conseguiu ler, sem nova busca ou localizacao inventada.
Esses leitores ja retornaram registros recentes em um Pager fisico 2.0.0-stable;
o usuario confirmou que os contadores Wi-Fi e BLE da Expedicao aumentaram.
O percurso completo com GPS, consumo e sincronizacao continua pendente.

**A coleta nao precisa de Internet.** Nas versoes anteriores, o Wi-Fi automatico
dependia de uma interface cliente livre, que pode desaparecer quando o Client
Mode e desativado. A 0.8.3 acrescenta uma alternativa: ler os APs recentes do
Recon original, sem mudar interfaces, canais ou a conexao de gerenciamento.
Essa alternativa exige banco nativo disponivel, formato reconhecido, modulo
sqlite3 e registros atualizados nos ultimos 30 segundos. Nao usa historico antigo
como descoberta atual nem inventa a criptografia quando faltam detalhes.

Na tela Expedição, as linhas **WiFi** e **BLE** agora mostram os resultados ou
falhas de cada radio separadamente. Falta de GPS nao apaga mais esses erros.
Dispositivos encontrados sem localizacao continuam locais, sem pontos no mapa.
Se o Bluetooth estiver desligado ou sem controlador, isso aparece na sua linha.
A busca implementada e **Bluetooth LE**; aparelhos Bluetooth classicos ou que
nao anunciam naquele momento podem nao aparecer, mesmo estando proximos.

**Se continuar tudo zerado:** feche o Hackomon, mantenha o Pager conectado ao
PC e abra **DIAGNOSTICAR.cmd** na pasta extraida. Informe a senha quando pedido.
O arquivo **DIAGNOSTICO-HACKOMON.txt** sera salvo na mesma pasta. Ele informa
interfaces/modos, estado do Bluetooth, contagens e idade dos registros do Recon,
GPS e os ultimos estados da coleta. Nao executa buscas nem altera configuracoes;
nao inclui nomes de redes, MACs, coordenadas, config, chaves ou capturas.
Esse relatorio permite adaptar o app ao que o seu firmware realmente apresenta.

Conecte seu GPS externo. Em **Settings > GPS**, selecione a porta, ajuste a
velocidade indicada pelo fabricante e use **Restart GPSd**. Confira o fix com
visao aberta do ceu antes do percurso. O procedimento e descrito pela
[Hak5](https://documentation.hak5.org/wifi-pineapple-pager/gps).

No SSH, rode o diagnostico sem abrir a tela nem iniciar coleta:

```sh
export PATH="/mmc/usr/bin:/mmc/usr/sbin:$PATH"
export LD_LIBRARY_PATH="/mmc/usr/lib:/mmc/lib:${LD_LIBRARY_PATH:-}"
python3 /root/payloads/user/games/hackomon/run_hackomon.py --doctor
```

`OK` na porta GPSd significa apenas que o servico atende. Nao comprova fix.
`OPCIONAL AUSENTE` nao impede o pet, mas impede a funcao correspondente.
O diagnostico nao busca redes, nao pareia aparelhos e nao envia dados.

Wi-Fi usa `iw` e `ip`; BLE usa `bluetoothctl`; inventario Bluetooth classico usa
`sdptool`. Antes de instalar qualquer ferramenta faltante, consulte os nomes
disponiveis nos feeds do seu firmware com `opkg list`. Nao reinstale BlueZ/GPSd
nem troque um pacote preinstalado apenas por aparecer uma sugestao generica.
O instalador cuida apenas das dependencias basicas do app; nao promete que
todas as ferramentas opcionais existam na 2.0.

No Hackomon, abra **Expedicao** e pressione A para iniciar. Fique parado
primeiro e confira GPS e descobertas. B volta ao pet mantendo a expedicao;
ESQ encerra e salva o resumo. GPS ausente ou impreciso nao gera posicoes falsas.
Wi-Fi e BLE alternam as buscas: nao cobrem todas as bandas ao mesmo tempo.
O Bluetooth implementado faz descoberta e inventario de servicos; mesh e
ataques genericos de pareamento nao estao implementados.

Os testes de laboratorio existentes dependem de selecao de um alvo autorizado,
radio compativel e ferramentas opcionais; nao comecam so por iniciar uma
expedicao. Veja [NETWORKS.md](NETWORKS.md) e [EXPEDITIONS.md](EXPEDITIONS.md)
na pasta `docs` do pacote. Nenhuma tentativa de senha foi comprovada neste
hardware. Captura incompleta, ferramenta ausente e teste inconclusivo devem
aparecer como tal.

## 6. Configure o WDGWars novamente

Depois do reset talvez seja necessario recuperar sua chave. Pelo SSH:

```sh
mkdir -p /mmc/root/hackomon
test -f /mmc/root/hackomon/config.json || cp /root/payloads/user/games/hackomon/config.example.json /mmc/root/hackomon/config.json
chmod 600 /mmc/root/hackomon/config.json
vi /mmc/root/hackomon/config.json
```

Coloque sua chave no campo `wdgwars_api_key`, somente nesse arquivo local.
Nao envie a chave no chat ou ao GitHub. Se o Wi-Fi nao encontrar uma interface
livre, ajuste `wifi_interface` para a interface real indicada pelo `iw dev`;
nao escolha a interface que mantem sua conexao de gerenciamento.

No app, abra **Redes > WDGWars**, valide a conta e confira o nome retornado.
So depois escolha sincronizar e confirme o envio de descobertas com localizacao.
Capturas e senhas ficam locais. A validacao real da conta e do recebimento
ainda precisa desse teste. Detalhes: `docs/WDGWARS.md` no ZIP.

## Se o tema ficar pendente

O app pode ter sido instalado com sucesso mesmo que o tema seja recusado.
O instalador informa essa diferenca e retorna codigo 3. Casos comuns:

- **Tema ja existe:** uma copia Hackomon reconhecida e valida e preservada automaticamente;
  uma pasta desconhecida fica pendente para nao sobrescrever suas alteracoes.
- **Base nao encontrada:** localize no SSH com `find /lib/pager/themes /root /usr/share /rom/root -name theme.json 2>/dev/null`.
- **Formato/layout diferente:** nao force o instalador; preserve a base e envie
  o erro para adaptar o overlay ao formato realmente instalado.

Para conferir uma base encontrada, sem alterar arquivos:

```sh
python3 /mmc/root/hackomon-setup-0.10.1/tools/install_theme.py --base /caminho/real/wargames --dry-run
```

Se a conferencia passar, repita sem `--dry-run`. Para uma segunda copia,
adicione `--name hackomon-field-test`. O instalador nunca sobrescreve uma
pasta existente nem seleciona o tema por voce.

## Reverter e preservar dados

Selecione `wargames` para voltar ao visual original. O app continua independente.
O save fica em `/mmc/root/hackomon/state.json`; a pasta tambem guarda expedicoes,
configuracao e evidencias privadas. Faca copia dela antes de outro factory reset.
Nao publique o tema montado no Pager como MIT: ele contem a sua base Hak5
licenciada. O ZIP distribuido aqui contem apenas o overlay original e o app.

## Se a conexao pedir atencao

**A versao anterior mostrou PRONTO, mas o jogo pediu PAGERCTL:** a 0.8.2 corrige
o iniciador, que buscava a biblioteca junto da copia temporaria do script.
Reaplique esta versao abrindo INSTALAR.cmd na nova pasta extraida. Python ja
instalado e reaproveitado; save/config e tema valido sao preservados. Nao e
necessario instalar o payload de demonstracao PAGERCTL separadamente.
O iniciador agora usa `_PAYLOAD_HOME`, a pasta real fornecida pela Hak5, conforme
a [documentacao oficial](https://documentation.hak5.org/wifi-pineapple-pager/payloads-1/speedrunning-payload-dev#loading-additional-content).

**Pager nao encontrado:** confira USB-C de dados ou Wi-Fi de gerenciamento e
SSH em Settings > System > SSH. Depois abra INSTALAR.cmd novamente.

**Senha incorreta:** use a senha de sistema criada depois do reset. Ela nao e
necessariamente a mesma senha do AP de gerenciamento.

**Identidade SSH alterada depois do reset:** confirme que esta conectado ao
seu Pager e confira sua identidade antes de remover a entrada antiga. Nesse
caso especifico, abra o PowerShell e rode:

```powershell
ssh-keygen -R 172.16.52.1
```

Depois abra INSTALAR.cmd novamente e confira a nova identidade. O instalador
nao desativa a verificacao SSH nem remove identidades automaticamente.

**Falta OpenSSH ou tar.exe:** use o Cliente OpenSSH e o tar do Windows 10/11.
A instalacao manual alternativa esta em `docs/INSTALL.md`. O instalador nao
pede privilegios de administrador para instalar componentes do Windows.

**Validacao desta entrega:** transferencia binaria e fluxo Windows testados
com um servidor local simulado, inclusive repeticao, caminhos com espacos e
falhas. Isso nao valida autenticacao interativa, radios ou execucao no Pager real.
