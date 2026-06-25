export default function TopBar({ screen, onNav }) {
  return (
    <div className="topbar">
      <div className="logo">
        <span className="mark">🛡️</span>
        <span className="product">Scout</span>
        <span className="chip">by AX · echo</span>
      </div>
      <div className="topnav">
        <a className={screen === "dash" ? "active" : ""} onClick={() => onNav("dash")}>
          Codebases
        </a>
        <a className={screen === "ws" ? "active" : ""} onClick={() => onNav("ws")}>
          Workspace
        </a>
        <a>Docs</a>
      </div>
      <div className="avatar" />
    </div>
  );
}
