// Gera o Pac-Man do perfil SEM o action do autor: usa só a biblioteca (que não envia nada a terceiros)
// e lê o calendário de contribuições pela API GraphQL do GitHub com o token do workflow.
// Uso: GITHUB_TOKEN=... node gerar.mjs <usuario> <pasta-de-saida>
import fs from 'fs';
import { ArcadeRenderer } from 'pacman-contribution-graph';

const [usuario, saida = 'pacman'] = process.argv.slice(2);
const token = process.env.GITHUB_TOKEN;
if (!usuario || !token) {
	console.error('uso: GITHUB_TOKEN=... node gerar.mjs <usuario> <pasta>');
	process.exit(1);
}
fs.mkdirSync(saida, { recursive: true });

const gerar = (tema) =>
	new Promise((ok, erro) => {
		let svg = '';
		new ArcadeRenderer({
			game: 'pacman',
			platform: 'github',
			username: usuario,
			gameTheme: tema,
			playerStyle: 'opportunistic',
			showMonthLabels: true,
			githubSettings: { accessToken: token },
			svgCallback: (s) => (svg = s),
			gameOverCallback: () => ok(svg),
			pointsIncreasedCallback: () => {}
		})
			.start()
			.catch(erro);
	});

for (const [tema, arq] of [['github', 'pacman.svg'], ['github-dark', 'pacman-escuro.svg']]) {
	const svg = await gerar(tema);
	fs.writeFileSync(`${saida}/${arq}`, svg);
	console.log(`${saida}/${arq}: ${(svg.length / 1024).toFixed(0)} KB`);
}
