# Notas basicas de dados e privacidade

- A startup fornece diretamente somente dados empresariais agregados necessarios.
- Nao coletar CPF, nomes de funcionarios, salarios individuais, clientes identificados ou contatos pessoais.
- Dados reais, banco local, backups, exports e segredos ficam fora do Git e de `data/synthetic`.
- Proteger computador, disco e backup; testar restauracao antes do piloto.
- Compartilhamento institucional deve indicar destinatario, finalidade e escopo e ser conhecido pela startup.
- Prestacao do servico, pesquisa, benchmark e treinamento sao finalidades separadas.
- Pseudonimizacao nao deve ser chamada de anonimizacao.
- Antes de dados reais, registrar responsavel, retencao, procedimento de correcao/eliminacao e resposta a incidente.

Estas notas sao um checklist operacional inicial, nao parecer juridico.

## Rotina minima de backup

1. Encerre edicoes na aplicacao durante a copia.
2. Execute `python scripts/backup_local.py <destino-protegido>`; o script recusa sobrescrever um arquivo existente.
3. Mantenha o destino fora do repositorio, em volume cifrado e com acesso restrito.
4. Mensalmente, abra uma copia restaurada e execute o walkthrough/sanity check sem usar a base original.
