const { useMemo, useState } = React;

async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.ok === false) {
        throw new Error(data.message || "Request failed");
    }
    return data;
}

function DashboardApp({ initial }) {
    const [projects, setProjects] = useState(initial.projects || []);
    const [query, setQuery] = useState(initial.query || "");
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [editingId, setEditingId] = useState(null);
    const [editName, setEditName] = useState("");
    const [editDescription, setEditDescription] = useState("");
    const [error, setError] = useState("");

    async function handleSearch(e) {
        e.preventDefault();
        try {
            setError("");
            const data = await apiFetch(`/api/projects?q=${encodeURIComponent(query)}`);
            setProjects(data.projects || []);
        } catch (err) {
            setError(err.message);
        }
    }

    async function createProject(e) {
        e.preventDefault();
        try {
            setError("");
            const data = await apiFetch("/api/projects", {
                method: "POST",
                body: JSON.stringify({ name, description }),
            });
            setProjects((prev) => [data.project, ...prev]);
            setName("");
            setDescription("");
        } catch (err) {
            setError(err.message);
        }
    }

    function startEdit(project) {
        setEditingId(project.id);
        setEditName(project.name || "");
        setEditDescription(project.description || "");
    }

    async function saveEdit(projectId) {
        try {
            setError("");
            await apiFetch(`/api/projects/${projectId}`, {
                method: "PUT",
                body: JSON.stringify({ name: editName, description: editDescription }),
            });
            setProjects((prev) =>
                prev.map((p) => (p.id === projectId ? { ...p, name: editName, description: editDescription } : p))
            );
            setEditingId(null);
        } catch (err) {
            setError(err.message);
        }
    }

    async function removeProject(projectId) {
        if (!window.confirm("Delete this project and all tasks?")) return;
        try {
            setError("");
            await apiFetch(`/api/projects/${projectId}`, { method: "DELETE" });
            setProjects((prev) => prev.filter((p) => p.id !== projectId));
        } catch (err) {
            setError(err.message);
        }
    }

    return (
        <>
            <section className="page-head">
                <h1>Project Dashboard (React)</h1>
                <form className="search-form" onSubmit={handleSearch}>
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Search projects by name or description..."
                    />
                    <button className="btn" type="submit">Search</button>
                </form>
            </section>

            {error ? <div className="flash flash-error">{error}</div> : null}

            <section className="card form-panel">
                <h2>Create Project</h2>
                <form className="form-grid" onSubmit={createProject}>
                    <label>Project Name</label>
                    <input value={name} onChange={(e) => setName(e.target.value)} required />
                    <label>Description</label>
                    <textarea
                        rows="2"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Project goals, scope, notes..."
                    />
                    <button className="btn" type="submit">Create Project</button>
                </form>
            </section>

            <section className="projects-grid">
                {projects.length === 0 ? (
                    <div className="card"><p>No projects found. Create your first project above.</p></div>
                ) : null}
                {projects.map((project) => (
                    <article key={project.id} className="card project-card">
                        <a className="project-title" href={`/projects/${project.id}`}>{project.name}</a>
                        <p>{project.description || "No description provided."}</p>
                        <div className="progress-row">
                            <span>{project.done_tasks}/{project.total_tasks} tasks done</span>
                            <span>{Math.round(project.progress || 0)}%</span>
                        </div>
                        <div className="progress-bar">
                            <div className="progress-fill" style={{ width: `${project.progress || 0}%` }} />
                        </div>

                        {editingId === project.id ? (
                            <div className="form-grid">
                                <label>Name</label>
                                <input value={editName} onChange={(e) => setEditName(e.target.value)} />
                                <label>Description</label>
                                <textarea rows="2" value={editDescription} onChange={(e) => setEditDescription(e.target.value)} />
                                <button className="btn" onClick={() => saveEdit(project.id)} type="button">Save</button>
                                <button className="btn btn-secondary" onClick={() => setEditingId(null)} type="button">Cancel</button>
                            </div>
                        ) : (
                            <button className="btn btn-secondary" type="button" onClick={() => startEdit(project)}>Edit Project</button>
                        )}

                        <button className="btn btn-danger w-full" type="button" onClick={() => removeProject(project.id)}>
                            Delete Project
                        </button>
                    </article>
                ))}
            </section>
        </>
    );
}

function TaskCard({ task, members, onEditTask, onDeleteTask, onCommentTask, onDragStart }) {
    const [editing, setEditing] = useState(false);
    const [comment, setComment] = useState("");
    const [form, setForm] = useState({
        title: task.title || "",
        description: task.description || "",
        due_date: task.due_date || "",
        priority: task.priority || "medium",
        status: task.status || "todo",
        assigned_to: task.assigned_to || "",
    });

    function updateField(key, value) {
        setForm((prev) => ({ ...prev, [key]: value }));
    }

    async function submitEdit(e) {
        e.preventDefault();
        await onEditTask(task.id, form);
        setEditing(false);
    }

    async function submitComment(e) {
        e.preventDefault();
        if (!comment.trim()) return;
        await onCommentTask(task.id, comment.trim());
        setComment("");
    }

    return (
        <article className="task-card" draggable onDragStart={() => onDragStart(task.id)}>
            <div className="task-head">
                <strong>{task.title}</strong>
                <span className={`badge badge-${task.priority}`}>{(task.priority || "").toUpperCase()}</span>
            </div>
            <p>{task.description || "No description."}</p>
            <p><b>Due:</b> {task.due_date || "Not set"}</p>
            <p><b>Assigned:</b> {task.assignee_name || "Unassigned"}</p>
            <p><b>Created by:</b> {task.creator_name}</p>

            {editing ? (
                <form className="form-grid" onSubmit={submitEdit}>
                    <label>Title</label>
                    <input value={form.title} onChange={(e) => updateField("title", e.target.value)} required />
                    <label>Description</label>
                    <textarea rows="2" value={form.description} onChange={(e) => updateField("description", e.target.value)} />
                    <label>Due Date</label>
                    <input type="date" value={form.due_date || ""} onChange={(e) => updateField("due_date", e.target.value)} />
                    <label>Priority</label>
                    <select value={form.priority} onChange={(e) => updateField("priority", e.target.value)}>
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                    </select>
                    <label>Status</label>
                    <select value={form.status} onChange={(e) => updateField("status", e.target.value)}>
                        <option value="todo">To Do</option>
                        <option value="in_progress">In Progress</option>
                        <option value="done">Done</option>
                    </select>
                    <label>Assign To</label>
                    <select value={form.assigned_to || ""} onChange={(e) => updateField("assigned_to", e.target.value)}>
                        <option value="">Unassigned</option>
                        {members.map((m) => (
                            <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                    </select>
                    <button className="btn btn-sm" type="submit">Save Task</button>
                    <button className="btn btn-secondary btn-sm" type="button" onClick={() => setEditing(false)}>Cancel</button>
                </form>
            ) : (
                <div className="form-inline">
                    <button className="btn btn-secondary btn-sm" type="button" onClick={() => setEditing(true)}>Edit Task</button>
                    <button className="btn btn-danger btn-sm" type="button" onClick={() => onDeleteTask(task.id)}>Delete Task</button>
                </div>
            )}

            <div className="comments">
                <h4>Comments</h4>
                {(task.comments || []).length === 0 ? <p className="muted">No comments yet.</p> : null}
                {(task.comments || []).map((comment) => (
                    <div key={comment.id} className="comment-item">
                        <b>{comment.author_name}</b>: {comment.content}
                        <span className="muted"> {comment.created_at}</span>
                    </div>
                ))}
                <form className="form-inline" onSubmit={submitComment}>
                    <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Write a comment..." />
                    <button className="btn btn-sm" type="submit">Comment</button>
                </form>
            </div>
        </article>
    );
}

function ProjectApp({ initial }) {
    const [payload, setPayload] = useState(initial.project_payload);
    const [error, setError] = useState("");
    const [taskForm, setTaskForm] = useState({
        title: "",
        description: "",
        due_date: "",
        priority: "medium",
        assigned_to: "",
    });
    const [memberToAdd, setMemberToAdd] = useState("");
    const [draggingTaskId, setDraggingTaskId] = useState(null);

    const projectId = initial.project_id;
    const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
    const labels = { todo: "To Do", in_progress: "In Progress", done: "Done" };

    async function refreshProject() {
        try {
            const data = await apiFetch(`/api/projects/${projectId}`);
            setPayload(data.payload);
            setError("");
        } catch (err) {
            setError(err.message);
        }
    }

    function updateTaskForm(key, value) {
        setTaskForm((prev) => ({ ...prev, [key]: value }));
    }

    async function createTask(e) {
        e.preventDefault();
        try {
            await apiFetch(`/api/projects/${projectId}/tasks`, {
                method: "POST",
                body: JSON.stringify(taskForm),
            });
            setTaskForm({ title: "", description: "", due_date: "", priority: "medium", assigned_to: "" });
            refreshProject();
        } catch (err) {
            setError(err.message);
        }
    }

    async function editTask(taskId, fields) {
        try {
            await apiFetch(`/api/tasks/${taskId}`, {
                method: "PUT",
                body: JSON.stringify(fields),
            });
            refreshProject();
        } catch (err) {
            setError(err.message);
        }
    }

    async function deleteTask(taskId) {
        if (!window.confirm("Delete task?")) return;
        try {
            await apiFetch(`/api/tasks/${taskId}`, { method: "DELETE" });
            refreshProject();
        } catch (err) {
            setError(err.message);
        }
    }

    async function addComment(taskId, content) {
        try {
            await apiFetch(`/api/tasks/${taskId}/comments`, {
                method: "POST",
                body: JSON.stringify({ content }),
            });
            refreshProject();
        } catch (err) {
            setError(err.message);
        }
    }

    async function addMember() {
        if (!memberToAdd) return;
        try {
            await apiFetch(`/api/projects/${projectId}/members`, {
                method: "POST",
                body: JSON.stringify({ user_id: Number(memberToAdd) }),
            });
            setMemberToAdd("");
            refreshProject();
        } catch (err) {
            setError(err.message);
        }
    }

    async function removeMember(memberId) {
        try {
            await apiFetch(`/api/projects/${projectId}/members/${memberId}`, { method: "DELETE" });
            refreshProject();
        } catch (err) {
            setError(err.message);
        }
    }

    async function moveTask(taskId, newStatus) {
        const previous = payload;
        const next = JSON.parse(JSON.stringify(payload));
        const statuses = ["todo", "in_progress", "done"];
        let movedTask = null;
        statuses.forEach((status) => {
            next.status_groups[status] = (next.status_groups[status] || []).filter((task) => {
                if (task.id === taskId) {
                    movedTask = { ...task, status: newStatus };
                    return false;
                }
                return true;
            });
        });
        if (movedTask) next.status_groups[newStatus].unshift(movedTask);
        setPayload(next);

        try {
            await apiFetch(`/api/tasks/${taskId}/move`, {
                method: "POST",
                body: JSON.stringify({ status: newStatus }),
            });
        } catch (err) {
            setPayload(previous);
            setError(err.message);
        }
    }

    return (
        <>
            <section className="page-head">
                <div>
                    <h1>{payload.project.name} (React)</h1>
                    <p>{payload.project.description || "No description."}</p>
                </div>
                <a className="btn" href="/dashboard">Back to Dashboard</a>
            </section>

            {error ? <div className="flash flash-error">{error}</div> : null}

            <section className="two-col">
                <article className="card">
                    <h2>Create Task</h2>
                    <form className="form-grid" onSubmit={createTask}>
                        <label>Title</label>
                        <input value={taskForm.title} onChange={(e) => updateTaskForm("title", e.target.value)} required />
                        <label>Description</label>
                        <textarea rows="2" value={taskForm.description} onChange={(e) => updateTaskForm("description", e.target.value)} />
                        <label>Due Date</label>
                        <input type="date" min={today} value={taskForm.due_date} onChange={(e) => updateTaskForm("due_date", e.target.value)} />
                        <label>Priority</label>
                        <select value={taskForm.priority} onChange={(e) => updateTaskForm("priority", e.target.value)}>
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                        </select>
                        <label>Assign To</label>
                        <select value={taskForm.assigned_to} onChange={(e) => updateTaskForm("assigned_to", e.target.value)}>
                            <option value="">Unassigned</option>
                            {payload.members.map((member) => (
                                <option key={member.id} value={member.id}>{member.name} ({member.email})</option>
                            ))}
                        </select>
                        <button className="btn" type="submit">Create Task</button>
                    </form>
                </article>

                <article className="card">
                    <h2>Team Collaboration</h2>
                    <p>Members can update tasks and leave comments.</p>
                    <div className="member-list">
                        {payload.members.map((member) => (
                            <div key={member.id} className="member-row">
                                <span>{member.name} ({member.email})</span>
                                {payload.is_owner && member.id !== payload.project.owner_id ? (
                                    <button className="btn btn-danger btn-sm" type="button" onClick={() => removeMember(member.id)}>Remove</button>
                                ) : null}
                            </div>
                        ))}
                    </div>
                    {payload.is_owner ? (
                        <div className="form-inline mt-8">
                            <select value={memberToAdd} onChange={(e) => setMemberToAdd(e.target.value)}>
                                <option value="">Add user to project...</option>
                                {payload.non_members.map((user) => (
                                    <option key={user.id} value={user.id}>{user.name} ({user.email})</option>
                                ))}
                            </select>
                            <button className="btn" type="button" onClick={addMember}>Add Member</button>
                        </div>
                    ) : null}
                </article>
            </section>

            <section className="board">
                {["todo", "in_progress", "done"].map((status) => (
                    <div key={status} className="column" data-status={status}>
                        <h3>{labels[status]}</h3>
                        <div
                            className="dropzone"
                            onDragOver={(e) => e.preventDefault()}
                            onDrop={(e) => {
                                e.preventDefault();
                                if (draggingTaskId) moveTask(draggingTaskId, status);
                                setDraggingTaskId(null);
                            }}
                        >
                            {(payload.status_groups[status] || []).map((task) => (
                                <TaskCard
                                    key={task.id}
                                    task={task}
                                    members={payload.members}
                                    onEditTask={editTask}
                                    onDeleteTask={deleteTask}
                                    onCommentTask={addComment}
                                    onDragStart={setDraggingTaskId}
                                />
                            ))}
                        </div>
                    </div>
                ))}
            </section>
        </>
    );
}

function App() {
    const initial = window.__INITIAL_DATA__ || {};
    if (initial.view === "project") return <ProjectApp initial={initial} />;
    return <DashboardApp initial={initial} />;
}

const root = ReactDOM.createRoot(document.getElementById("react-root"));
root.render(<App />);
