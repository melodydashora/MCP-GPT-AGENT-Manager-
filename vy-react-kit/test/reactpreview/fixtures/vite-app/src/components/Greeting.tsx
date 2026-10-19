type GreetingProps = { name: string };

export default function Greeting({ name }: GreetingProps) {
  const label: string = `Hello, ${name}`;
  return <h1 id="greeting">{label}</h1>;
}
