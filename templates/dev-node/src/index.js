// {{label}} — entrée
export function main() {
  console.log("Hello from {{name}}");
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
