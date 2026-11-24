import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import CardContent from '@mui/material/CardContent';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TableSortLabel from '@mui/material/TableSortLabel';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import useScreen from '../hooks/useScreen.js';

/**
 * Lists records: a table on large screens, cards on phones.
 * @param {Object} props Component props.
 * @returns {JSX.Element} The list.
 */
function DataList({
  label, rows, columns, linkTo = null, renderCard, sort = '', order = 'asc', onSort = null,
}) {
  const { isMobile } = useScreen();

  if (isMobile) {
    return (
      <Box sx={{ display: 'grid', gap: 2 }}>
        {rows.map((row) => (
          <Card key={row.id}>
            {linkTo ? (
              <CardActionArea component={Link} to={linkTo(row)}>
                <CardContent sx={{ display: 'grid', gap: 1 }}>{renderCard(row)}</CardContent>
              </CardActionArea>
            ) : (
              <CardContent sx={{ display: 'grid', gap: 1 }}>{renderCard(row)}</CardContent>
            )}
          </Card>
        ))}
      </Box>
    );
  }

  return (
    <TableContainer component={Paper}>
      <Table size="small" aria-label={label}>
        <TableHead>
          <TableRow>
            {columns.map((column) => (
              <TableCell
                key={column.label}
                align={column.align}
                sortDirection={column.sort && column.sort === sort ? order : false}
              >
                {column.sort && onSort ? (
                  <TableSortLabel
                    active={column.sort === sort}
                    direction={column.sort === sort ? order : 'asc'}
                    onClick={() => onSort(column.sort)}
                  >
                    {column.label}
                  </TableSortLabel>
                ) : column.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id} hover>
              {columns.map((column) => (
                <TableCell
                  key={column.label}
                  align={column.align}
                  sx={column.nowrap
                    ? { whiteSpace: 'nowrap' }
                    : { overflowWrap: 'anywhere' }}
                >
                  {column.render(row)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

DataList.propTypes = {
  label: PropTypes.string.isRequired,
  rows: PropTypes.arrayOf(PropTypes.shape({ id: PropTypes.number })).isRequired,
  columns: PropTypes.arrayOf(PropTypes.shape({
    label: PropTypes.string.isRequired,
    render: PropTypes.func.isRequired,
    sort: PropTypes.string,
    align: PropTypes.string,
    nowrap: PropTypes.bool,
  })).isRequired,
  linkTo: PropTypes.func,
  renderCard: PropTypes.func.isRequired,
  sort: PropTypes.string,
  order: PropTypes.oneOf(['asc', 'desc']),
  onSort: PropTypes.func,
};

export default DataList;
