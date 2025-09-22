# PRD.md

Sistema Orfin

## Sobre o MVP deste projeto

Esta API será o backend de um sistema de gerenciamento financeiro pessoal e familiar. A idéia central do Sistema Orfin é ser um SAAS onde os clientes poderão pagar por anuidade escolhendo dentre dois tipos de planos o pessoal e o familiar.
No plano pessoal o cliente terá acesso completo ao um sistema de controle financeiro único e exclusivamente para ele. Haverão telas de cadastro de contas, despesas, receitas e transações entre contas. Haverá tambem uma tela para cadastro de cartões de crédito e subsequentemente a tela para inserção de gastos da fatura de cartão, gastos simples e parcelados. Despesas e Receitas poderão ser cadastradas em repetição fixa ou por tempo determinado podendo ser definido em carater anual, mensal, semanal ou diário. A tela de transações que mostra tudo de receita despesas e cartões será a principal tela onde o usuário poderá selecionar o mês e ano e conforme o que for buscado no banco de dados (API) o frontend montará e mostrará a tela de forma calculada.
No plano familia contempla exatamente a mesma coisa do plano pessoal, contudo o sistema terá uma tela inicial de membro da família, similar a tela de perfil toda vez que abrimos o Netflix. Para cada membro da família escolhido teremos um sistema totalmente separado com dados unicos de cada membro. Teremos um limite de apenas 3 perfis e um perfil chamado familia que não terá cadastros apenas informações somadas computando todos os membros da familia como um só.
Esse sistema deverá ter uma autenticação com JWT Token e usar uma aplicação externa para manter as assinaturas como um Stripe. O usuário tem acesso imediato a aplicação após registrado pagamento. A autenticação expira após 24hr, ou seja após isto é necessário logar novamente. No futuro será implementado OAuth2 com Google e outros.
Essa aplicação terá banco de dados Postgres e quando chegar o momento de colocar em produção deverá ser colocada na AWS.
