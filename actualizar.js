const fs = require("fs");
const Parser = require("rss-parser");

const parser = new Parser();

async function main() {

const feeds = [
"https://openai.com/news/rss.xml",
"https://blog.google/technology/ai/rss/",
"https://huggingface.co/blog/feed.xml"
];

let noticias = [];

for (const feed of feeds) {

try {

const data = await parser.parseURL(feed);

data.items.slice(0,5).forEach(item=>{

noticias.push({
titulo:item.title,
link:item.link,
fecha:item.pubDate,
fuente:data.title
});

});

} catch(e){

console.log("Error:",e.message);

}

}

fs.writeFileSync(
"noticias.json",
JSON.stringify(noticias,null,2)
);

console.log("✅ Noticias actualizadas:",noticias.length);

}

main();
