export default function Home() {
  return (
    <main>
      <header>
        <h1>Claudina</h1>
        <small>Active now</small>
      </header>

      <div className="chat">
        <p>hey, how are you?</p>
      </div>

      <form>
        <input placeholder="Message..." />
        <button>Send</button>
      </form>
    </main>
  );
}