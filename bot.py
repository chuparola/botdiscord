import asyncio
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os

from produtos import PRODUTOS
from pix import criar_pix, verificar_pix
from database import init_db, criar_pedido, listar_pendentes, atualizar_status

load_dotenv()

TOKEN = 'MTQ3NjIxNDM2MzYzODczMDg1NA.G-c3J-.ljU4gGwmBrGLH30WUN6AfkK0kTJXkZCih-QuuE'
CARGO_ID = 1476304982096482335
GUILD_ID = 1475929306973732896

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================= FUNÇÃO AUXILIAR =================
async def criar_canal_pagamento(guild, member, pix_data, categoria=None):
    canal = await guild.create_text_channel(
        name=f"pagamento-{member.name.lower()}",
        category=categoria,
        overwrites={
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True),
            guild.me or guild.get_member(bot.user.id): discord.PermissionOverwrite(view_channel=True),
        }
    )
    embed = discord.Embed(
        title="🧾 Revisão do Pedido",
        description=f"**{pix_data['nome']}**",
        color=0x2b2d31
    )
    embed.add_field(name="Valor", value=f"R$ {pix_data['valor']:.2f}", inline=False)
    embed.add_field(name="Status", value="Aguardando pagamento", inline=False)

    await canal.send(embed=embed, view=PagamentoView(pix_data))

# ================= VIEW PAGAMENTO =================
class PagamentoView(discord.ui.View):
    def __init__(self, pix_data):
        super().__init__(timeout=None)
        self.pix_data = pix_data

    @discord.ui.button(label="💸 Ir para o Pagamento", style=discord.ButtonStyle.green)
    async def pagar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # SEM defer + followup
        await interaction.response.send_message(
            f"🔐 Código Pix:\n```{self.pix_data['pix']['point_of_interaction']['transaction_data']['qr_code']}```",
            ephemeral=True
        )

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.red)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Pedido cancelado.", ephemeral=True)
        button.disabled = True
        await interaction.message.edit(view=self)
        if interaction.channel:
            await interaction.channel.delete()

# ================= SELECT PRODUTO =================
class ProdutoSelect(discord.ui.Select):
    def __init__(self, produto_key):
        self.produto_key = produto_key
        produto = PRODUTOS[produto_key]
        options = [
            discord.SelectOption(
                label=info["label"],
                description=f"R$ {info['preco']:.2f}",
                value=opcao_key
            ) for opcao_key, info in produto["opcoes"].items()
        ]
        super().__init__(placeholder="Escolha uma opção", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # 1️⃣ ACK IMEDIATO
        await interaction.response.defer(ephemeral=True)

        opcao_key = self.values[0]
        produto = PRODUTOS[self.produto_key]
        opcao = produto["opcoes"][opcao_key]

        nome = f"{produto['titulo']} - {opcao['label']}"
        preco = opcao["preco"]

        # 2️⃣ CHAMADA BLOQUEANTE FORA DO LOOP
        loop = asyncio.get_running_loop()
        pix = await loop.run_in_executor(None, criar_pix, preco, nome)

        pix_data = {"pix": pix, "nome": nome, "valor": preco}
        await criar_pedido(
            interaction.user.id,
            interaction.user.display_name,
            pix["id"]
        )

        # 3️⃣ RESPOSTA FINAL (UMA SÓ)
        await interaction.followup.send(
            "✅ Pedido criado! Abrindo seu canal privado...",
            ephemeral=True
        )

        # 4️⃣ CRIA CANAL SEM USAR interaction
        asyncio.create_task(
            criar_canal_pagamento(
                interaction.guild,
                interaction.user,
                pix_data,
                interaction.channel.category
            )
        )

# ================= VIEW PRODUTO =================
class ProdutoView(discord.ui.View):
    def __init__(self, produto_key):
        super().__init__(timeout=None)
        self.add_item(ProdutoSelect(produto_key))

# ================= FUNÇÃO ABRIR PRODUTO =================
async def abrir_produto(ctx, produto_key):
    produto = PRODUTOS[produto_key]
    embed = discord.Embed(
        title=produto["titulo"],
        description=produto["descricao"],
        color=0x2b2d31
    )
    embed.set_image(url=produto["imagem"])
    await ctx.send(embed=embed, view=ProdutoView(produto_key))

# ===================== LOOP DE VERIFICAÇÃO PIX =====================
@tasks.loop(seconds=20)
async def verificar_pagamentos():
    pedidos = await listar_pendentes()
    for user_id, payment_id in pedidos:
        try:
            loop = asyncio.get_running_loop()
            status = await loop.run_in_executor(None, verificar_pix, payment_id)
        except Exception as e:
            print(f"Erro ao verificar Pix {payment_id}: {e}")
            continue

        if status != "approved":
            continue

        guild = bot.get_guild(GUILD_ID)
        if not guild:
            continue

        member = guild.get_member(user_id)
        cargo = guild.get_role(CARGO_ID)

        if not member or not cargo:
            continue

        try:
            await member.add_roles(cargo, reason="Pagamento aprovado")
            try:
                member = guild.get_member(user_id)

                if member:
                    await member.send(f"✅ Seu pagamento foi aprovado! {member.display_name}\nPor favor abra um ticket https://discord.com/channels/1475929306973732896/1475969245933338798")
                else:
                    await member.send(f"✅ Seu pagamento foi aprovado! {user_id}\nPor favor abra um ticket https://discord.com/channels/1475929306973732896/1475969245933338798")
                
            except discord.Forbidden:
                pass
        except discord.Forbidden:
            print("❌ Sem permissão para adicionar cargo.")

        await atualizar_status(payment_id, "approved")
        print(f"✅ Pagamento aprovado para {user_id}")

# ================= COMANDOS =================
@bot.command()
async def hashcolor(ctx):
    await abrir_produto(ctx, "hashcolor")

@bot.command()
async def hashfull(ctx):
    await abrir_produto(ctx, "hashfull")

@bot.command()
async def skinchanger(ctx):
    await abrir_produto(ctx, "skinchanger")

@bot.command()
async def strongeresp(ctx):
    await abrir_produto(ctx, "strongeresp")

@bot.command()
async def hashexternal(ctx):
    await abrir_produto(ctx, "hashexternal")

@bot.command()
async def akiracolor(ctx):
    await abrir_produto(ctx, "akiracolor")

@bot.command()
async def spooferunban(ctx):
    await abrir_produto(ctx, "spooferunban")

@bot.command()
async def spooferbypass(ctx):
    await abrir_produto(ctx, "spooferbypass")

# ================= BOT READY =================
@bot.event
async def on_ready():
    await init_db()  # inicializa DB
    verificar_pagamentos.start()
    print(f"🔥 Bot online como {bot.user}")

@bot.event
async def on_command_error(ctx, error):
    print(f"Erro comando: {error}")


bot.run(TOKEN)
