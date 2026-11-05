import React, { useState } from 'react';
import { IconButton } from '@mui/material';
import { CalendarMonthOutlined, ChevronLeft, ChevronRight } from '@mui/icons-material';

const WorkspaceCalendar = () => {
  const today = new Date();
  const [month, setMonth] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));
  const start = (month.getDay() + 6) % 7;
  const length = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const label = new Intl.DateTimeFormat('fr', { month: 'long', year: 'numeric' }).format(month);
  return (
    <section className="sis-calendar sis-panel" aria-label="Calendrier">
      <div className="sis-calendar__toolbar">
        <div className="sis-widget-heading"><CalendarMonthOutlined /><h2>Calendrier</h2></div>
        <div className="sis-calendar__heading">
          <IconButton aria-label="Mois précédent" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}><ChevronLeft /></IconButton>
          <h3 aria-live="polite" aria-label={label}>{new Intl.DateTimeFormat('fr', { month: 'short', year: 'numeric' }).format(month)}</h3>
          <IconButton aria-label="Mois suivant" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}><ChevronRight /></IconButton>
        </div>
      </div>
      <div className="sis-calendar__week" aria-hidden="true">
        {['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di'].map(day => <span key={day}>{day}</span>)}
      </div>
      <ol className="sis-calendar__days">
        {Array.from({ length }, (_, index) => {
          const day = index + 1;
          const current = day === today.getDate()
            && month.getMonth() === today.getMonth() && month.getFullYear() === today.getFullYear();
          return (
            <li key={day} style={day === 1 ? { gridColumnStart: start + 1 } : undefined}>
              <time
                dateTime={`${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`}
                aria-current={current ? 'date' : undefined}
                aria-label={new Intl.DateTimeFormat('fr', { dateStyle: 'full' }).format(new Date(month.getFullYear(), month.getMonth(), day))}
              >{day}
              </time>
            </li>
          );
        })}
      </ol>
    </section>
  );
};

export default WorkspaceCalendar;
