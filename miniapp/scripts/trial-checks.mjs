export function checkTrialEvidence(record) {
  const errors = []
  const metrics = {}
  if (!/^[0-9a-f]{40}$/.test(record?.buildCommit || '')) errors.push('Record the tested build commit')
  for (const [key, min, max] of [['walkthrough', 3, 5], ['closedTrial', 10, 20]]) {
    const stage = record?.[key]
    const participants = Array.isArray(stage?.participants) ? stage.participants : []
    if (stage?.status !== 'completed' || !Number.isFinite(Date.parse(stage?.date))) errors.push(`${key}: real test execution is not recorded`)
    if (participants.length < min || participants.length > max) errors.push(`${key}: requires ${min}–${max} real participants`)
    const ids = participants.map(item => item?.id)
    if (ids.some(id => !/^[A-Z][0-9]{2}$/.test(id || '')) || new Set(ids).size !== ids.length) errors.push(`${key}: unique anonymous participant IDs required`)
    let completed = 0
    for (const person of participants) {
      if (person?.medicalMisunderstanding !== false || person?.allergenExclusionConfirmed !== true) errors.push(`${key}/${person?.id}: unresolved safety observation`)
      for (const taskName of ['today', 'pantry']) {
        const task = person?.tasks?.[taskName]
        if (typeof task?.completed !== 'boolean' || !Number.isFinite(task?.seconds) || task.seconds < 0) errors.push(`${key}/${person?.id}/${taskName}: missing observed task result`)
        else if (task.completed) completed++
      }
    }
    const total = participants.length * 2
    const completionRate = total ? completed / total : 0
    metrics[key] = { participants: participants.length, completed, total, completionRate }
    if (completionRate < 0.9) errors.push(`${key}: core task completion below 90%`)
  }
  if (record?.defectAuditCompleted !== true || !Array.isArray(record?.defects)) errors.push('Defect audit is incomplete; an empty list is not evidence of zero defects')
  for (const defect of Array.isArray(record?.defects) ? record.defects : []) {
    if (!defect?.id || !['P0', 'P1', 'P2', 'P3'].includes(defect?.priority) || !['open', 'closed'].includes(defect?.status) || !defect?.evidence?.trim()) errors.push('Defect classification, status and evidence are required')
    if (['P0', 'P1'].includes(defect?.priority) && defect?.status !== 'closed') errors.push(`${defect?.id}: unresolved ${defect?.priority} defect`)
  }
  for (const id of ['weixin-devtools', 'android', 'ios', 'weak-network', 'permissions']) {
    const check = record?.deviceChecks?.find(item => item?.id === id)
    if (check?.status !== 'passed' || !check?.evidence?.trim()) errors.push(`${id}: verified device/network evidence is missing`)
  }
  for (const role of ['professional-content', 'safety', 'privacy', 'real-users', 'release-owner']) {
    const signoff = record?.signoffs?.find(item => item?.role === role)
    if (signoff?.status !== 'approved' || !signoff?.name?.trim() || !signoff?.evidence?.trim() || !Number.isFinite(Date.parse(signoff?.date))) errors.push(`${role}: real approval is missing`)
  }
  return { passed: errors.length === 0, metrics, errors }
}
