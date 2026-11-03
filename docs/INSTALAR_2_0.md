# Hackomon 0.8.0: instalar depois do reset

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

No PowerShell do Windows, confirme que consegue entrar:

```powershell
ssh root@172.16.52.1
```

Use a senha criada no primeiro inicio. Digite `exit` para voltar ao Windows.
O IP de gerenciamento e a conta sao os documentados pela
[Hak5 para SSH](https://documentation.hak5.org/wifi-pineapple-pager/connecting-to-the-wifi-pineapple-pager/ssh-and-the-wifi-pineapple-pager).

Se o reset gerar um aviso de chave SSH diferente, confirme que esta conectado
ao seu Pager e confira a identidade antes de retirar a entrada antiga:

```powershell
ssh-keygen -R 172.16.52.1
```

## 2. Instale pelo Windows

Baixe **hackomon-instalar-0.8.0.zip** e extraia **tudo** para uma pasta.
Abra o PowerShell nessa pasta, que contem `payload`, `themes` e `tools`.
Execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Instalar-Hackomon.ps1
```

Essa opcao de execucao vale apenas para esse processo. O script e local e
pode ser lido antes de executar; nao executa um script baixado da Internet.
Se surgir pergunta sobre a identidade do Pager, confira antes de aceitar.
A senha pode ser solicitada nas etapas de conexao, copia e instalacao.

O instalador:

- baixa **libpagerctl.so** diretamente do projeto PAGERCTL, em revisao fixa,
  e compara seu SHA-256 antes de enviar; o binario nao vem dentro deste ZIP;
- copia os arquivos para `/mmc/root/hackomon-setup-0.8.0`;
- instala Python 3 + ctypes **somente se faltarem**, pelos feeds que ja estao
  configurados no Pager, usando `opkg install -d mmc`;
- verifica importacoes e carrega a biblioteca sem abrir a tela;
- instala o app em `/root/payloads/user/games/hackomon`;
- preserva um payload anterior em `/mmc/root/hackomon-backups/` e nao altera
  o save nem a configuracao em `/mmc/root/hackomon`;
- cria `/root/themes/hackomon-field` a partir do Wargames **local** do firmware.

A base original e procurada primeiro em `/lib/pager/themes/wargames`, conforme
o [README oficial do Wargames](https://github.com/hak5/wifipineapplepager-themes/blob/master/themes/wargames/README).
Ela e somente lida; todos os arquivos personalizados ficam na nova pasta.

Nao atualiza em massa pacotes do sistema, nao troca feeds e nao instala drivers.
A instalacao de pacotes segue o destino MMC recomendado pela
[Hak5](https://documentation.hak5.org/wifi-pineapple-pager/external-packages).
A biblioteca fixada e de terceiros; integridade e API nao comprovam compatibilidade
com o firmware 2.0. Se o carregamento falhar, a instalacao para com o erro.

Sem tema, por exemplo numa segunda instalacao com o tema ja criado:

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

- **Tema ja existe:** selecione o existente; para atualizar so o app, use `-SkipTheme`.
- **Base nao encontrada:** localize no SSH com `find /lib/pager/themes /root /usr/share /rom/root -name theme.json 2>/dev/null`.
- **Formato/layout diferente:** nao force o instalador; preserve a base e envie
  o erro para adaptar o overlay ao formato realmente instalado.

Para conferir uma base encontrada, sem alterar arquivos:

```sh
python3 /mmc/root/hackomon-setup-0.8.0/tools/install_theme.py --base /caminho/real/wargames --dry-run
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
